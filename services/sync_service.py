"""
Comprehensive Sync Service for BioEntry Terminal
Handles bidirectional synchronization between terminal and API server.

IMPORTANT: This service manages all data synchronization including:
- User database downloads from server
- Offline record uploads to server
- Configuration synchronization
- Automatic sync scheduling with retry logic
"""

import asyncio
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import asdict
import threading
import time

from services.api_client import get_api_client, BulkRecord, APIResponse
from core.database_manager import get_database_manager
from utils.config import get_config
from utils.logger import get_logger
from utils.state_manager import get_state_manager


class SyncService:
    """
    Complete synchronization service for BioEntry terminal.
    
    This service handles:
    - Automatic sync scheduling
    - User database synchronization (download from server)
    - Access records synchronization (upload to server)
    - Retry logic for failed synchronizations
    - Sync status tracking and reporting
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.db_manager = get_database_manager()
        self.api_client = get_api_client()
        self.state_manager = get_state_manager()
        
        # Sync configuration
        self.auto_sync_enabled = True
        self.sync_interval = self.config.sync.interval_minutes * 60  # Convert to seconds
        self.max_retry_attempts = self.config.sync.max_retry_attempts
        self.retry_delay_base = self.config.sync.retry_delay_seconds
        
        # Sync state
        self.last_user_sync = None
        self.last_records_sync = None
        self.sync_in_progress = False
        self.sync_task = None
        
        # Statistics
        self.sync_stats = {
            'total_syncs': 0,
            'successful_syncs': 0,
            'failed_syncs': 0,
            'last_sync_duration': 0,
            'users_synced': 0,
            'records_synced': 0
        }
        
        self.logger.info("Sync service initialized")
    
    # ==========================================
    # AUTO SYNC MANAGEMENT
    # ==========================================
    
    async def start_auto_sync(self):
        """
        Start automatic synchronization background task.
        This should be called once during terminal initialization.
        """
        if self.sync_task and not self.sync_task.done():
            self.logger.warning("Auto sync already running")
            return
        
        self.auto_sync_enabled = True
        self.sync_task = asyncio.create_task(self._auto_sync_loop())
        self.logger.info(f"Auto sync started with {self.sync_interval}s interval")
    
    async def stop_auto_sync(self):
        """Stop automatic synchronization"""
        self.auto_sync_enabled = False
        
        if self.sync_task and not self.sync_task.done():
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
        
        self.logger.info("Auto sync stopped")
    
    async def _auto_sync_loop(self):
        """Main auto sync loop"""
        while self.auto_sync_enabled:
            try:
                # Check if we're online before attempting sync
                if await self.api_client.check_connectivity():
                    await self.perform_full_sync()
                else:
                    self.logger.debug("Skipping sync - terminal is offline")
                
                # Wait for next sync interval
                await asyncio.sleep(self.sync_interval)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in auto sync loop: {str(e)}")
                await asyncio.sleep(self.sync_interval)
        
        self.logger.info("Auto sync loop terminated")
    
    # ==========================================
    # FULL SYNCHRONIZATION
    # ==========================================
    
    async def perform_full_sync(self) -> Dict[str, Any]:
        """
        Perform complete bidirectional synchronization.
        
        Returns:
            Dictionary with sync results and statistics
        """
        if self.sync_in_progress:
            return {'status': 'already_in_progress'}
        
        self.sync_in_progress = True
        sync_start_time = time.time()
        
        results = {
            'status': 'success',
            'timestamp': datetime.utcnow().isoformat(),
            'user_sync': None,
            'records_sync': None,
            'duration': 0,
            'errors': []
        }
        
        try:
            self.logger.info("Starting full synchronization")
            
            # Step 1: Sync users from server (download)
            try:
                user_sync_result = await self.sync_users_from_server()
                results['user_sync'] = user_sync_result
            except Exception as e:
                error_msg = f"User sync failed: {str(e)}"
                self.logger.error(error_msg)
                results['errors'].append(error_msg)
            
            # Step 2: Sync records to server (upload)
            try:
                records_sync_result = await self.sync_records_to_server()
                results['records_sync'] = records_sync_result
            except Exception as e:
                error_msg = f"Records sync failed: {str(e)}"
                self.logger.error(error_msg)
                results['errors'].append(error_msg)
            
            # Update statistics
            sync_duration = time.time() - sync_start_time
            results['duration'] = sync_duration
            
            if results['errors']:
                results['status'] = 'partial_success'
                self.sync_stats['failed_syncs'] += 1
            else:
                self.sync_stats['successful_syncs'] += 1
            
            self.sync_stats['total_syncs'] += 1
            self.sync_stats['last_sync_duration'] = sync_duration
            
            self.logger.info(f"Full sync completed in {sync_duration:.2f}s with status: {results['status']}")
            
        except Exception as e:
            results['status'] = 'failed'
            results['errors'].append(f"Full sync failed: {str(e)}")
            self.sync_stats['failed_syncs'] += 1
            self.sync_stats['total_syncs'] += 1
            self.logger.error(f"Full synchronization failed: {str(e)}")
        
        finally:
            self.sync_in_progress = False
        
        return results
    
    # ==========================================
    # USER DATABASE SYNCHRONIZATION
    # ==========================================
    
    async def sync_users_from_server(self) -> Dict[str, Any]:
        """
        Synchronize user database from server.
        Downloads users and updates local database.
        
        Returns:
            Dictionary with sync results
        """
        self.logger.info("Starting user database synchronization")
        
        # Get last sync timestamp
        last_sync = self.last_user_sync.isoformat() if self.last_user_sync else None
        
        # Request user data from server
        response = await self.api_client.sync_user_database(last_sync)
        
        if not response.success:
            raise Exception(f"Failed to fetch user database: {response.error}")
        
        server_data = response.data
        users = server_data.get('records', [])
        
        if not users:
            self.logger.info("No user updates available")
            return {
                'status': 'no_updates',
                'users_processed': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Process user records
        processed_users = 0
        failed_users = []
        
        for user_record in users:
            try:
                # Convert API format to local database format
                user_data = {
                    'cedula': user_record.get('c'),  # Cedula (compressed field name)
                    'nombre': user_record.get('n'),  # Nombre (compressed field name)
                    'empresa': user_record.get('e'),  # Empresa (compressed field name)
                    'slot': user_record.get('s'),    # Slot (compressed field name)
                    'last_updated': datetime.utcnow().isoformat(),
                    'synced': True
                }
                
                # Save or update user in local database
                await self.db_manager.save_or_update_user(user_data)
                processed_users += 1
                
            except Exception as e:
                failed_users.append({
                    'cedula': user_record.get('c', 'unknown'),
                    'error': str(e)
                })
                self.logger.error(f"Failed to process user {user_record.get('c')}: {str(e)}")
        
        # Update sync timestamp
        self.last_user_sync = datetime.utcnow()
        
        # Update statistics
        self.sync_stats['users_synced'] = processed_users
        
        result = {
            'status': 'success' if not failed_users else 'partial_success',
            'users_processed': processed_users,
            'users_failed': len(failed_users),
            'failed_users': failed_users,
            'sync_timestamp': server_data.get('sync_timestamp'),
            'total_server_records': server_data.get('total_records', 0),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"User sync completed: {processed_users} users processed, {len(failed_users)} failed")
        return result
    
    # ==========================================
    # RECORDS SYNCHRONIZATION
    # ==========================================
    
    async def sync_records_to_server(self) -> Dict[str, Any]:
        """
        Synchronize access records to server.
        Uploads unsynced records from local database.
        
        Returns:
            Dictionary with sync results
        """
        self.logger.info("Starting records synchronization to server")
        
        # Get unsynced records from local database
        unsynced_records = await self.db_manager.get_unsynced_records()
        
        if not unsynced_records:
            self.logger.info("No records to sync")
            return {
                'status': 'no_records',
                'records_processed': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Convert local records to API format
        bulk_records = []
        for record in unsynced_records:
            try:
                # Get user information for the record
                user_info = await self.db_manager.get_user_by_cedula(record.get('cedula', ''))
                
                bulk_record = BulkRecord(
                    user_id=record.get('user_id'),
                    cedula=record.get('cedula', ''),
                    employee_name=user_info.get('nombre', 'Unknown') if user_info else 'Unknown',
                    access_timestamp=record.get('timestamp', ''),
                    method=record.get('method', 'offline'),
                    verification_type=record.get('verification_type', 'facial'),
                    confidence_score=record.get('confidence_score'),
                    device_id=self.config.api.terminal_id,
                    location_name=record.get('location_name', 'Terminal'),
                    terminal_record_id=record.get('id', ''),
                    created_at=record.get('created_at', record.get('timestamp', ''))
                )
                
                bulk_records.append(bulk_record)
                
            except Exception as e:
                self.logger.error(f"Failed to convert record {record.get('id')}: {str(e)}")
                continue
        
        if not bulk_records:
            self.logger.warning("No valid records to sync after conversion")
            return {
                'status': 'no_valid_records',
                'records_processed': 0,
                'timestamp': datetime.utcnow().isoformat()
            }
        
        # Upload records in batches
        batch_size = self.config.sync.batch_size
        total_processed = 0
        total_failed = 0
        failed_records = []
        
        for i in range(0, len(bulk_records), batch_size):
            batch = bulk_records[i:i + batch_size]
            
            try:
                # Upload batch to server
                response = await self.api_client.upload_bulk_records(batch)
                
                if response.success:
                    batch_result = response.data
                    processed = batch_result.get('summary', {}).get('processed_successfully', 0)
                    failed = batch_result.get('summary', {}).get('failed', 0)
                    
                    total_processed += processed
                    total_failed += failed
                    
                    # Mark successfully uploaded records as synced
                    for processed_record in batch_result.get('processed_records', []):
                        terminal_record_id = processed_record.get('terminal_record_id')
                        if terminal_record_id:
                            await self.db_manager.mark_record_as_synced(terminal_record_id)
                    
                    # Track failed records
                    failed_records.extend(batch_result.get('failed_records', []))
                    
                    self.logger.info(f"Batch uploaded: {processed} processed, {failed} failed")
                    
                else:
                    # Entire batch failed
                    self.logger.error(f"Batch upload failed: {response.error}")
                    total_failed += len(batch)
                    failed_records.extend([{'terminal_record_id': r.terminal_record_id, 'error': response.error} for r in batch])
                
            except Exception as e:
                self.logger.error(f"Error uploading batch: {str(e)}")
                total_failed += len(batch)
                failed_records.extend([{'terminal_record_id': r.terminal_record_id, 'error': str(e)} for r in batch])
        
        # Update sync timestamp
        self.last_records_sync = datetime.utcnow()
        
        # Update statistics
        self.sync_stats['records_synced'] = total_processed
        
        result = {
            'status': 'success' if total_failed == 0 else 'partial_success',
            'records_processed': total_processed,
            'records_failed': total_failed,
            'failed_records': failed_records,
            'total_records': len(unsynced_records),
            'timestamp': datetime.utcnow().isoformat()
        }
        
        self.logger.info(f"Records sync completed: {total_processed} processed, {total_failed} failed")
        return result
    
    # ==========================================
    # MANUAL SYNC OPERATIONS
    # ==========================================
    
    async def force_user_sync(self) -> Dict[str, Any]:
        """Force immediate user database synchronization"""
        self.logger.info("Forcing user database sync")
        return await self.sync_users_from_server()
    
    async def force_records_sync(self) -> Dict[str, Any]:
        """Force immediate records synchronization"""
        self.logger.info("Forcing records sync")
        return await self.sync_records_to_server()
    
    async def clear_sync_history(self):
        """Clear sync timestamps (forces full sync on next attempt)"""
        self.last_user_sync = None
        self.last_records_sync = None
        self.logger.info("Sync history cleared")
    
    # ==========================================
    # STATUS AND STATISTICS
    # ==========================================
    
    def get_sync_status(self) -> Dict[str, Any]:
        """
        Get current synchronization status and statistics.
        
        Returns:
            Dictionary with sync status information
        """
        return {
            'auto_sync_enabled': self.auto_sync_enabled,
            'sync_in_progress': self.sync_in_progress,
            'sync_interval': self.sync_interval,
            'last_user_sync': self.last_user_sync.isoformat() if self.last_user_sync else None,
            'last_records_sync': self.last_records_sync.isoformat() if self.last_records_sync else None,
            'statistics': self.sync_stats.copy(),
            'configuration': {
                'max_retry_attempts': self.max_retry_attempts,
                'retry_delay_base': self.retry_delay_base,
                'batch_size': self.config.sync.batch_size
            }
        }
    
    async def get_pending_sync_counts(self) -> Dict[str, int]:
        """
        Get count of items pending synchronization.
        
        Returns:
            Dictionary with pending counts
        """
        try:
            unsynced_records = await self.db_manager.get_unsynced_records()
            
            return {
                'pending_records': len(unsynced_records),
                'needs_user_sync': await self._needs_user_sync(),
                'last_check': datetime.utcnow().isoformat()
            }
        except Exception as e:
            self.logger.error(f"Error getting pending sync counts: {str(e)}")
            return {
                'pending_records': 0,
                'needs_user_sync': False,
                'error': str(e)
            }
    
    async def _needs_user_sync(self) -> bool:
        """Check if user database synchronization is needed"""
        try:
            response = await self.api_client.check_sync_status()
            if response.success:
                return response.data.get('needs_sync', False)
            return True  # Default to needing sync if we can't check
        except:
            return True


# Global sync service instance
_sync_service = None


def get_sync_service() -> SyncService:
    """Get the global sync service instance"""
    global _sync_service
    if _sync_service is None:
        _sync_service = SyncService()
    return _sync_service


if __name__ == "__main__":
    # Test the sync service
    import asyncio
    
    async def test_sync_service():
        sync_service = get_sync_service()
        
        # Test sync status
        print("Testing sync status...")
        status = sync_service.get_sync_status()
        print(f"Sync status: {status}")
        
        # Test pending counts
        print("Testing pending counts...")
        pending = await sync_service.get_pending_sync_counts()
        print(f"Pending counts: {pending}")
        
        # Test connectivity-dependent operations
        api_client = get_api_client()
        if await api_client.check_connectivity():
            print("Testing user sync...")
            user_result = await sync_service.sync_users_from_server()
            print(f"User sync result: {user_result}")
        else:
            print("Offline - skipping online tests")
    
    asyncio.run(test_sync_service())
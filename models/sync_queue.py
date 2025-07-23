"""
Sync Queue Data Model for BioEntry Terminal
Manages synchronization queue for offline operations.
"""

from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
from enum import Enum
import json
import uuid


class SyncAction(Enum):
    """Types of synchronization actions."""
    CREATE_RECORD = "create_record"
    UPDATE_RECORD = "update_record"
    DELETE_RECORD = "delete_record"
    SYNC_USER = "sync_user"
    UPLOAD_IMAGE = "upload_image"


class SyncStatus(Enum):
    """Synchronization status."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRY = "retry"


@dataclass
class SyncQueueItem:
    """
    Individual item in the synchronization queue.
    
    Represents a single operation that needs to be synchronized with the server.
    """
    
    # Primary identification
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    # Action details
    action: SyncAction = SyncAction.CREATE_RECORD
    record_id: str = ""  # ID of the record to sync
    record_type: str = "access_record"  # Type of record (access_record, user, etc.)
    
    # Sync control
    status: SyncStatus = SyncStatus.PENDING
    priority: int = 1  # Higher number = higher priority
    
    # Retry logic
    attempts: int = 0
    max_attempts: int = 5
    next_retry_at: Optional[str] = None
    
    # Timestamps
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())
    last_attempt_at: Optional[str] = None
    completed_at: Optional[str] = None
    
    # Data and metadata
    data: Optional[Dict[str, Any]] = None  # Additional data for the sync operation
    error_message: Optional[str] = None
    server_response: Optional[Dict[str, Any]] = None
    
    def __post_init__(self):
        """Initialize computed fields after object creation."""
        if isinstance(self.action, str):
            self.action = SyncAction(self.action)
        if isinstance(self.status, str):
            self.status = SyncStatus(self.status)
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert sync queue item to dictionary format for database storage.
        
        Returns:
            Dictionary representation of sync queue item
        """
        return {
            'id': self.id,
            'action': self.action.value,
            'record_id': self.record_id,
            'record_type': self.record_type,
            'status': self.status.value,
            'priority': self.priority,
            'attempts': self.attempts,
            'max_attempts': self.max_attempts,
            'next_retry_at': self.next_retry_at,
            'created_at': self.created_at,
            'updated_at': self.updated_at,
            'last_attempt_at': self.last_attempt_at,
            'completed_at': self.completed_at,
            'data': json.dumps(self.data) if self.data else None,
            'error_message': self.error_message,
            'server_response': json.dumps(self.server_response) if self.server_response else None
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SyncQueueItem':
        """
        Create SyncQueueItem instance from dictionary data.
        
        Args:
            data: Dictionary with sync queue item data
            
        Returns:
            SyncQueueItem instance
        """
        # Parse JSON fields
        item_data = None
        if data.get('data'):
            try:
                item_data = json.loads(data['data'])
            except json.JSONDecodeError:
                pass
        
        server_response = None
        if data.get('server_response'):
            try:
                server_response = json.loads(data['server_response'])
            except json.JSONDecodeError:
                pass
        
        return cls(
            id=data.get('id', str(uuid.uuid4())),
            action=SyncAction(data.get('action', SyncAction.CREATE_RECORD.value)),
            record_id=data.get('record_id', ''),
            record_type=data.get('record_type', 'access_record'),
            status=SyncStatus(data.get('status', SyncStatus.PENDING.value)),
            priority=data.get('priority', 1),
            attempts=data.get('attempts', 0),
            max_attempts=data.get('max_attempts', 5),
            next_retry_at=data.get('next_retry_at'),
            created_at=data.get('created_at', datetime.utcnow().isoformat()),
            updated_at=data.get('updated_at', datetime.utcnow().isoformat()),
            last_attempt_at=data.get('last_attempt_at'),
            completed_at=data.get('completed_at'),
            data=item_data,
            error_message=data.get('error_message'),
            server_response=server_response
        )
    
    def start_attempt(self) -> None:
        """Mark sync attempt as started."""
        self.status = SyncStatus.IN_PROGRESS
        self.attempts += 1
        self.last_attempt_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        self.error_message = None
    
    def mark_completed(self, server_response: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark sync operation as completed successfully.
        
        Args:
            server_response: Optional server response data
        """
        self.status = SyncStatus.COMPLETED
        self.completed_at = datetime.utcnow().isoformat()
        self.updated_at = datetime.utcnow().isoformat()
        self.server_response = server_response
        self.error_message = None
        self.next_retry_at = None
    
    def mark_failed(self, error_message: str, schedule_retry: bool = True) -> None:
        """
        Mark sync operation as failed.
        
        Args:
            error_message: Error description
            schedule_retry: Whether to schedule a retry attempt
        """
        self.error_message = error_message
        self.updated_at = datetime.utcnow().isoformat()
        
        if schedule_retry and self.attempts < self.max_attempts:
            self.status = SyncStatus.RETRY
            # Calculate exponential backoff delay
            delay_minutes = min(2 ** self.attempts, 60)  # Cap at 60 minutes
            next_retry = datetime.utcnow() + timedelta(minutes=delay_minutes)
            self.next_retry_at = next_retry.isoformat()
        else:
            self.status = SyncStatus.FAILED
            self.next_retry_at = None
    
    def is_ready_for_retry(self) -> bool:
        """
        Check if item is ready for retry attempt.
        
        Returns:
            True if ready for retry, False otherwise
        """
        if self.status != SyncStatus.RETRY:
            return False
        
        if not self.next_retry_at:
            return True
        
        try:
            next_retry = datetime.fromisoformat(self.next_retry_at.replace('Z', '+00:00'))
            return datetime.utcnow() >= next_retry
        except:
            return True
    
    def can_retry(self) -> bool:
        """
        Check if item can be retried (hasn't exceeded max attempts).
        
        Returns:
            True if can retry, False otherwise
        """
        return self.attempts < self.max_attempts
    
    def get_age_minutes(self) -> int:
        """
        Get item age in minutes since creation.
        
        Returns:
            Age in minutes
        """
        try:
            created = datetime.fromisoformat(self.created_at.replace('Z', '+00:00'))
            now = datetime.utcnow()
            delta = now - created
            return int(delta.total_seconds() / 60)
        except:
            return 0
    
    def get_next_retry_minutes(self) -> Optional[int]:
        """
        Get minutes until next retry attempt.
        
        Returns:
            Minutes until retry, or None if no retry scheduled
        """
        if not self.next_retry_at:
            return None
        
        try:
            next_retry = datetime.fromisoformat(self.next_retry_at.replace('Z', '+00:00'))
            now = datetime.utcnow()
            delta = next_retry - now
            return max(0, int(delta.total_seconds() / 60))
        except:
            return None
    
    def __str__(self) -> str:
        """String representation of sync queue item."""
        return f"SyncQueueItem(id={self.id}, action={self.action.value}, status={self.status.value})"
    
    def __repr__(self) -> str:
        """Detailed string representation of sync queue item."""
        return (f"SyncQueueItem(id={self.id}, action={self.action.value}, "
                f"record_id={self.record_id}, status={self.status.value}, "
                f"attempts={self.attempts}/{self.max_attempts})")


@dataclass
class SyncQueueStats:
    """Statistics for the sync queue."""
    
    total_items: int = 0
    pending_items: int = 0
    in_progress_items: int = 0
    completed_items: int = 0
    failed_items: int = 0
    retry_items: int = 0
    
    # Priority breakdown
    high_priority_pending: int = 0
    normal_priority_pending: int = 0
    
    # Age statistics
    oldest_item_minutes: int = 0
    newest_item_minutes: int = 0
    
    # Performance metrics  
    success_rate: float = 0.0
    average_attempts: float = 0.0
    
    @classmethod
    def from_items(cls, items: List[SyncQueueItem]) -> 'SyncQueueStats':
        """
        Calculate statistics from list of sync queue items.
        
        Args:
            items: List of SyncQueueItem objects
            
        Returns:
            SyncQueueStats object with calculated statistics
        """
        if not items:
            return cls()
        
        stats = cls()
        stats.total_items = len(items)
        
        ages = []
        total_attempts = 0
        
        for item in items:
            # Count by status
            if item.status == SyncStatus.PENDING:
                stats.pending_items += 1
                if item.priority > 1:
                    stats.high_priority_pending += 1
                else:
                    stats.normal_priority_pending += 1
            elif item.status == SyncStatus.IN_PROGRESS:
                stats.in_progress_items += 1
            elif item.status == SyncStatus.COMPLETED:
                stats.completed_items += 1
            elif item.status == SyncStatus.FAILED:
                stats.failed_items += 1
            elif item.status == SyncStatus.RETRY:
                stats.retry_items += 1
            
            # Collect age and attempts
            ages.append(item.get_age_minutes())
            total_attempts += item.attempts
        
        # Calculate age statistics
        if ages:
            stats.oldest_item_minutes = max(ages)
            stats.newest_item_minutes = min(ages)
        
        # Calculate performance metrics
        if stats.total_items > 0:
            stats.success_rate = stats.completed_items / stats.total_items
            stats.average_attempts = total_attempts / stats.total_items
        
        return stats


def create_record_sync_item(record_id: str, 
                           action: SyncAction = SyncAction.CREATE_RECORD,
                           priority: int = 1,
                           additional_data: Optional[Dict[str, Any]] = None) -> SyncQueueItem:
    """
    Create a sync queue item for record synchronization.
    
    Args:
        record_id: ID of the record to sync
        action: Type of sync action
        priority: Priority level (higher = more urgent)
        additional_data: Additional data for the sync operation
        
    Returns:
        SyncQueueItem for record synchronization
    """
    return SyncQueueItem(
        action=action,
        record_id=record_id,
        record_type="access_record",
        priority=priority,
        data=additional_data
    )


def create_user_sync_item(user_id: str, 
                         action: SyncAction = SyncAction.SYNC_USER,
                         priority: int = 2) -> SyncQueueItem:
    """
    Create a sync queue item for user synchronization.
    
    Args:
        user_id: ID of the user to sync
        action: Type of sync action
        priority: Priority level
        
    Returns:
        SyncQueueItem for user synchronization
    """
    return SyncQueueItem(
        action=action,
        record_id=user_id,
        record_type="user",
        priority=priority
    )


def create_bulk_sync_items(record_ids: List[str], 
                          action: SyncAction = SyncAction.CREATE_RECORD,
                          priority: int = 1) -> List[SyncQueueItem]:
    """
    Create multiple sync queue items for bulk operations.
    
    Args:
        record_ids: List of record IDs to sync
        action: Type of sync action
        priority: Priority level
        
    Returns:
        List of SyncQueueItem objects
    """
    return [
        create_record_sync_item(record_id, action, priority)
        for record_id in record_ids
    ]


if __name__ == "__main__":
    # Test sync queue model
    print("Testing SyncQueue model...")
    
    # Create test sync item
    item = create_record_sync_item("test_record_123")
    print(f"Created sync item: {item}")
    
    # Test attempt progression
    item.start_attempt()
    print(f"After start attempt: status={item.status.value}, attempts={item.attempts}")
    
    # Test failure with retry
    item.mark_failed("Network error", schedule_retry=True)
    print(f"After failure: status={item.status.value}, next_retry={item.next_retry_at}")
    
    # Test retry readiness
    print(f"Ready for retry: {item.is_ready_for_retry()}")
    print(f"Can retry: {item.can_retry()}")
    
    # Test completion
    item.mark_completed({"server_id": "srv_123"})
    print(f"After completion: status={item.status.value}, completed_at={item.completed_at}")
    
    # Test dictionary conversion
    item_dict = item.to_dict()
    print(f"Item dict keys: {list(item_dict.keys())}")
    
    # Test from dictionary
    item_from_dict = SyncQueueItem.from_dict(item_dict)
    print(f"Item from dict: {item_from_dict}")
    
    # Test bulk creation
    bulk_items = create_bulk_sync_items(["rec1", "rec2", "rec3"])
    print(f"Created {len(bulk_items)} bulk items")
    
    # Test statistics
    test_items = [
        create_record_sync_item("rec1"),
        create_record_sync_item("rec2", priority=2),
        create_user_sync_item("user1")
    ]
    test_items[0].mark_completed()
    test_items[1].mark_failed("Test error")
    
    stats = SyncQueueStats.from_items(test_items)
    print(f"Queue stats: total={stats.total_items}, completed={stats.completed_items}, "
          f"failed={stats.failed_items}, success_rate={stats.success_rate:.2%}")
    
    print("SyncQueue model tests completed successfully!")
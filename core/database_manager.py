import sqlite3
import asyncio
import aiosqlite
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
import uuid
from contextlib import asynccontextmanager

from utils.config import get_config
from utils.logger import get_logger, get_error_logger


class DatabaseManager:
    """
    Gestor de base de datos SQLite local para el terminal.
    Implementa el patrón Local-First con sincronización posterior.
    """
    
    def __init__(self):
        self.config = get_config()
        self.logger = get_logger()
        self.error_logger = get_error_logger()
        self.db_path = self.config.get_full_database_path()
        self._initialized = False
        
        # Crear directorio de base de datos si no existe
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def initialize(self) -> None:
        """Inicializa la base de datos y crea las tablas necesarias"""
        if self._initialized:
            return
        
        try:
            async with aiosqlite.connect(self.db_path) as db:
                # Crear tablas
                await self._create_tables(db)
                
                # Crear índices
                await self._create_indexes(db)
                
                # Configurar pragmas para optimización
                await self._configure_pragmas(db)
                
                await db.commit()
            
            self._initialized = True
            self.logger.info("Base de datos inicializada exitosamente", db_path=str(self.db_path))
            
        except Exception as e:
            self.error_logger.log_database_error("initialize", e)
            raise
    
    async def _create_tables(self, db: aiosqlite.Connection) -> None:
        """Crea todas las tablas necesarias"""
        
        # Tabla de usuarios
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT UNIQUE NOT NULL,
                document_id TEXT UNIQUE NOT NULL,
                name TEXT NOT NULL,
                department TEXT,
                position TEXT,
                company TEXT DEFAULT 'principal',
                fingerprint_template_id INTEGER,
                photo_hash TEXT,
                is_active BOOLEAN DEFAULT 1,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                synced_at TIMESTAMP
            )
        """)
        
        # Tabla de registros de acceso
        await db.execute("""
            CREATE TABLE IF NOT EXISTS access_records (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                server_id TEXT,
                user_id INTEGER,
                document_id TEXT NOT NULL,
                employee_name TEXT NOT NULL,
                access_timestamp TIMESTAMP NOT NULL,
                method TEXT NOT NULL,
                verification_type TEXT NOT NULL,
                confidence_score REAL,
                device_id TEXT NOT NULL,
                location_name TEXT,
                
                -- Campos de sincronización
                is_synced BOOLEAN DEFAULT 0,
                sync_attempts INTEGER DEFAULT 0,
                last_sync_attempt TIMESTAMP,
                sync_error_message TEXT,
                
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users (id)
            )
        """)
        
        # Tabla de cola de sincronización
        await db.execute("""
            CREATE TABLE IF NOT EXISTS sync_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                record_id INTEGER,
                record_type TEXT NOT NULL,
                action TEXT NOT NULL,
                payload TEXT NOT NULL,
                attempts INTEGER DEFAULT 0,
                max_attempts INTEGER DEFAULT 5,
                last_attempt TIMESTAMP,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (record_id) REFERENCES access_records (id)
            )
        """)
        
        # Tabla de configuración terminal
        await db.execute("""
            CREATE TABLE IF NOT EXISTS terminal_config (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Tabla de métricas de rendimiento
        await db.execute("""
            CREATE TABLE IF NOT EXISTS performance_metrics (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                metric_name TEXT NOT NULL,
                value REAL NOT NULL,
                unit TEXT DEFAULT 'ms',
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            )
        """)
    
    async def _create_indexes(self, db: aiosqlite.Connection) -> None:
        """Crea índices para optimizar consultas"""
        indexes = [
            "CREATE INDEX IF NOT EXISTS idx_users_document ON users(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_fingerprint ON users(fingerprint_template_id)",
            "CREATE INDEX IF NOT EXISTS idx_users_active ON users(is_active)",
            
            "CREATE INDEX IF NOT EXISTS idx_access_records_timestamp ON access_records(access_timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_access_records_user ON access_records(user_id)",
            "CREATE INDEX IF NOT EXISTS idx_access_records_document ON access_records(document_id)",
            "CREATE INDEX IF NOT EXISTS idx_access_records_sync ON access_records(is_synced, sync_attempts)",
            "CREATE INDEX IF NOT EXISTS idx_access_records_method ON access_records(method)",
            
            "CREATE INDEX IF NOT EXISTS idx_sync_queue_status ON sync_queue(status, attempts)",
            "CREATE INDEX IF NOT EXISTS idx_sync_queue_record ON sync_queue(record_id)",
            
            "CREATE INDEX IF NOT EXISTS idx_performance_timestamp ON performance_metrics(timestamp)",
            "CREATE INDEX IF NOT EXISTS idx_performance_metric ON performance_metrics(metric_name)"
        ]
        
        for index_sql in indexes:
            await db.execute(index_sql)
    
    async def _configure_pragmas(self, db: aiosqlite.Connection) -> None:
        """Configura pragmas de SQLite para optimización"""
        pragmas = [
            "PRAGMA journal_mode = WAL",
            "PRAGMA synchronous = NORMAL",
            "PRAGMA cache_size = 10000",
            "PRAGMA temp_store = MEMORY",
            "PRAGMA mmap_size = 268435456",  # 256MB
            "PRAGMA foreign_keys = ON"
        ]
        
        for pragma in pragmas:
            await db.execute(pragma)
    
    @asynccontextmanager
    async def get_connection(self):
        """Context manager para obtener conexión a la base de datos"""
        if not self._initialized:
            await self.initialize()
        
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            yield db
    
    # ==================== GESTIÓN DE USUARIOS ====================
    
    async def create_user(self, user_data: Dict[str, Any]) -> int:
        """Crea un nuevo usuario en la base de datos local"""
        try:
            async with self.get_connection() as db:
                sql = """
                    INSERT INTO users (
                        employee_id, document_id, name, department, position, 
                        company, fingerprint_template_id, photo_hash
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                cursor = await db.execute(sql, (
                    user_data.get("employee_id"),
                    user_data["document_id"],
                    user_data["name"],
                    user_data.get("department"),
                    user_data.get("position"),
                    user_data.get("company", "principal"),
                    user_data.get("fingerprint_template_id"),
                    user_data.get("photo_hash")
                ))
                
                await db.commit()
                user_id = cursor.lastrowid
                
                self.logger.info(
                    "Usuario creado exitosamente",
                    user_id=user_id,
                    document_id=user_data["document_id"],
                    name=user_data["name"]
                )
                
                return user_id
                
        except Exception as e:
            self.error_logger.log_database_error("create_user", e, user_data=user_data)
            raise
    
    async def get_user_by_document_id(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un usuario por su número de documento"""
        try:
            async with self.get_connection() as db:
                sql = """
                    SELECT * FROM users 
                    WHERE document_id = ? AND is_active = 1
                """
                
                async with db.execute(sql, (document_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return dict(row)
                    return None
                    
        except Exception as e:
            self.error_logger.log_database_error("get_user_by_document_id", e, document_id=document_id)
            raise
    
    async def get_user_by_fingerprint_id(self, template_id: int) -> Optional[Dict[str, Any]]:
        """
        CRÍTICO: Obtiene un usuario por su template_id del sensor AS608.
        Esta función es clave para el modo offline.
        """
        try:
            async with self.get_connection() as db:
                sql = """
                    SELECT * FROM users 
                    WHERE fingerprint_template_id = ? AND is_active = 1
                """
                
                async with db.execute(sql, (template_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        user_data = dict(row)
                        self.logger.debug(
                            "Usuario encontrado por template_id",
                            template_id=template_id,
                            user_id=user_data["id"],
                            document_id=user_data["document_id"]
                        )
                        return user_data
                    
                    self.logger.warning(
                        "Usuario no encontrado por template_id",
                        template_id=template_id
                    )
                    return None
                    
        except Exception as e:
            self.error_logger.log_database_error("get_user_by_fingerprint_id", e, template_id=template_id)
            raise
    
    async def update_user_fingerprint(self, user_id: int, template_id: int, quality_score: Optional[int] = None) -> bool:
        """Actualiza el template_id de huella de un usuario"""
        try:
            async with self.get_connection() as db:
                sql = """
                    UPDATE users 
                    SET fingerprint_template_id = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE id = ?
                """
                
                cursor = await db.execute(sql, (template_id, user_id))
                await db.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(
                        "Template de huella actualizado",
                        user_id=user_id,
                        template_id=template_id,
                        quality_score=quality_score
                    )
                    return True
                else:
                    self.logger.warning("Usuario no encontrado para actualizar template", user_id=user_id)
                    return False
                    
        except Exception as e:
            self.error_logger.log_database_error("update_user_fingerprint", e, user_id=user_id, template_id=template_id)
            raise
    
    async def get_all_users(self, active_only: bool = True) -> List[Dict[str, Any]]:
        """Obtiene todos los usuarios"""
        try:
            async with self.get_connection() as db:
                sql = "SELECT * FROM users"
                if active_only:
                    sql += " WHERE is_active = 1"
                sql += " ORDER BY name"
                
                async with db.execute(sql) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
                    
        except Exception as e:
            self.error_logger.log_database_error("get_all_users", e)
            raise
    
    # ==================== GESTIÓN DE REGISTROS DE ACCESO ====================
    
    async def create_access_record(self, record_data: Dict[str, Any]) -> int:
        """
        CRÍTICO: Crea un registro de acceso - SIEMPRE local primero.
        Esta es la función más importante para el patrón Local-First.
        """
        try:
            async with self.get_connection() as db:
                sql = """
                    INSERT INTO access_records (
                        server_id, user_id, document_id, employee_name, 
                        access_timestamp, method, verification_type, 
                        confidence_score, device_id, location_name
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                
                cursor = await db.execute(sql, (
                    record_data.get("server_id"),
                    record_data.get("user_id"),
                    record_data["document_id"],
                    record_data["employee_name"],
                    record_data["access_timestamp"],
                    record_data["method"],
                    record_data["verification_type"],
                    record_data.get("confidence_score"),
                    record_data["device_id"],
                    record_data.get("location_name")
                ))
                
                await db.commit()
                record_id = cursor.lastrowid
                
                self.logger.info(
                    "Registro de acceso creado",
                    record_id=record_id,
                    document_id=record_data["document_id"],
                    method=record_data["method"],
                    verification_type=record_data["verification_type"]
                )
                
                return record_id
                
        except Exception as e:
            self.error_logger.log_database_error("create_access_record", e, record_data=record_data)
            raise
    
    async def get_last_record_by_user(self, document_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene el último registro de un usuario específico"""
        try:
            async with self.get_connection() as db:
                sql = """
                    SELECT * FROM access_records 
                    WHERE document_id = ? 
                    ORDER BY access_timestamp DESC 
                    LIMIT 1
                """
                
                async with db.execute(sql, (document_id,)) as cursor:
                    row = await cursor.fetchone()
                    
                    if row:
                        return dict(row)
                    return None
                    
        except Exception as e:
            self.error_logger.log_database_error("get_last_record_by_user", e, document_id=document_id)
            raise
    
    async def get_pending_sync_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Obtiene registros pendientes de sincronización"""
        try:
            async with self.get_connection() as db:
                sql = """
                    SELECT * FROM access_records 
                    WHERE is_synced = 0 AND sync_attempts < 5
                    ORDER BY access_timestamp ASC
                    LIMIT ?
                """
                
                async with db.execute(sql, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
                    
        except Exception as e:
            self.error_logger.log_database_error("get_pending_sync_records", e)
            raise
    
    async def mark_record_as_synced(self, record_id: int, server_id: Optional[str] = None) -> bool:
        """Marca un registro como sincronizado exitosamente"""
        try:
            async with self.get_connection() as db:
                sql = """
                    UPDATE access_records 
                    SET is_synced = 1, 
                        server_id = ?,
                        last_sync_attempt = CURRENT_TIMESTAMP
                    WHERE id = ?
                """
                
                cursor = await db.execute(sql, (server_id, record_id))
                await db.commit()
                
                if cursor.rowcount > 0:
                    self.logger.info(
                        "Registro marcado como sincronizado",
                        record_id=record_id,
                        server_id=server_id
                    )
                    return True
                else:
                    self.logger.warning("Registro no encontrado para marcar como sincronizado", record_id=record_id)
                    return False
                    
        except Exception as e:
            self.error_logger.log_database_error("mark_record_as_synced", e, record_id=record_id)
            raise
    
    async def increment_sync_attempts(self, record_id: int, error_message: Optional[str] = None) -> bool:
        """Incrementa el contador de intentos de sincronización"""
        try:
            async with self.get_connection() as db:
                sql = """
                    UPDATE access_records 
                    SET sync_attempts = sync_attempts + 1,
                        last_sync_attempt = CURRENT_TIMESTAMP,
                        sync_error_message = ?
                    WHERE id = ?
                """
                
                cursor = await db.execute(sql, (error_message, record_id))
                await db.commit()
                
                if cursor.rowcount > 0:
                    self.logger.debug(
                        "Intentos de sincronización incrementados",
                        record_id=record_id,
                        error_message=error_message
                    )
                    return True
                else:
                    self.logger.warning("Registro no encontrado para incrementar intentos", record_id=record_id)
                    return False
                    
        except Exception as e:
            self.error_logger.log_database_error("increment_sync_attempts", e, record_id=record_id)
            raise
    
    async def get_records_by_date_range(self, start_date: datetime, end_date: datetime) -> List[Dict[str, Any]]:
        """Obtiene registros en un rango de fechas"""
        try:
            async with self.get_connection() as db:
                sql = """
                    SELECT * FROM access_records 
                    WHERE access_timestamp BETWEEN ? AND ?
                    ORDER BY access_timestamp DESC
                """
                
                async with db.execute(sql, (start_date.isoformat(), end_date.isoformat())) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
                    
        except Exception as e:
            self.error_logger.log_database_error("get_records_by_date_range", e)
            raise
    
    # ==================== GESTIÓN DE COLA DE SINCRONIZACIÓN ====================
    
    async def add_to_sync_queue(self, record_id: int, record_type: str, action: str, payload: Dict[str, Any]) -> int:
        """Agrega un elemento a la cola de sincronización"""
        try:
            async with self.get_connection() as db:
                sql = """
                    INSERT INTO sync_queue (record_id, record_type, action, payload)
                    VALUES (?, ?, ?, ?)
                """
                
                cursor = await db.execute(sql, (
                    record_id,
                    record_type,
                    action,
                    json.dumps(payload)
                ))
                
                await db.commit()
                queue_id = cursor.lastrowid
                
                self.logger.debug(
                    "Elemento añadido a cola de sincronización",
                    queue_id=queue_id,
                    record_id=record_id,
                    record_type=record_type,
                    action=action
                )
                
                return queue_id
                
        except Exception as e:
            self.error_logger.log_database_error("add_to_sync_queue", e)
            raise
    
    async def get_pending_sync_queue_items(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Obtiene elementos pendientes de la cola de sincronización"""
        try:
            async with self.get_connection() as db:
                sql = """
                    SELECT * FROM sync_queue 
                    WHERE status = 'pending' AND attempts < max_attempts
                    ORDER BY created_at ASC
                    LIMIT ?
                """
                
                async with db.execute(sql, (limit,)) as cursor:
                    rows = await cursor.fetchall()
                    return [dict(row) for row in rows]
                    
        except Exception as e:
            self.error_logger.log_database_error("get_pending_sync_queue_items", e)
            raise
    
    async def mark_sync_queue_item_as_completed(self, queue_id: int) -> bool:
        """Marca un elemento de la cola como completado"""
        try:
            async with self.get_connection() as db:
                sql = """
                    UPDATE sync_queue 
                    SET status = 'completed', last_attempt = CURRENT_TIMESTAMP
                    WHERE id = ?
                """
                
                cursor = await db.execute(sql, (queue_id,))
                await db.commit()
                
                return cursor.rowcount > 0
                
        except Exception as e:
            self.error_logger.log_database_error("mark_sync_queue_item_as_completed", e)
            raise
    
    async def increment_sync_queue_attempts(self, queue_id: int, error_message: Optional[str] = None) -> bool:
        """Incrementa los intentos de un elemento de la cola"""
        try:
            async with self.get_connection() as db:
                sql = """
                    UPDATE sync_queue 
                    SET attempts = attempts + 1,
                        last_attempt = CURRENT_TIMESTAMP,
                        error_message = ?
                    WHERE id = ?
                """
                
                cursor = await db.execute(sql, (error_message, queue_id))
                await db.commit()
                
                return cursor.rowcount > 0
                
        except Exception as e:
            self.error_logger.log_database_error("increment_sync_queue_attempts", e)
            raise
    
    # ==================== UTILIDADES Y MANTENIMIENTO ====================
    
    async def get_database_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la base de datos"""
        try:
            async with self.get_connection() as db:
                stats = {}
                
                # Contar usuarios
                async with db.execute("SELECT COUNT(*) FROM users WHERE is_active = 1") as cursor:
                    stats["active_users"] = (await cursor.fetchone())[0]
                
                # Contar registros
                async with db.execute("SELECT COUNT(*) FROM access_records") as cursor:
                    stats["total_records"] = (await cursor.fetchone())[0]
                
                # Contar registros no sincronizados
                async with db.execute("SELECT COUNT(*) FROM access_records WHERE is_synced = 0") as cursor:
                    stats["pending_sync_records"] = (await cursor.fetchone())[0]
                
                # Contar elementos en cola
                async with db.execute("SELECT COUNT(*) FROM sync_queue WHERE status = 'pending'") as cursor:
                    stats["pending_queue_items"] = (await cursor.fetchone())[0]
                
                # Registros de hoy
                today = datetime.now().date()
                async with db.execute(
                    "SELECT COUNT(*) FROM access_records WHERE DATE(access_timestamp) = ?",
                    (today,)
                ) as cursor:
                    stats["today_records"] = (await cursor.fetchone())[0]
                
                return stats
                
        except Exception as e:
            self.error_logger.log_database_error("get_database_stats", e)
            raise
    
    async def cleanup_old_records(self, days: int = 30) -> int:
        """Limpia registros antiguos según la configuración"""
        try:
            cutoff_date = datetime.now() - timedelta(days=days)
            
            async with self.get_connection() as db:
                # Solo limpiar registros ya sincronizados
                sql = """
                    DELETE FROM access_records 
                    WHERE access_timestamp < ? AND is_synced = 1
                """
                
                cursor = await db.execute(sql, (cutoff_date.isoformat(),))
                await db.commit()
                
                deleted_count = cursor.rowcount
                
                if deleted_count > 0:
                    self.logger.info(
                        "Registros antiguos limpiados",
                        deleted_count=deleted_count,
                        cutoff_date=cutoff_date.isoformat()
                    )
                
                return deleted_count
                
        except Exception as e:
            self.error_logger.log_database_error("cleanup_old_records", e)
            raise
    
    async def vacuum_database(self) -> None:
        """Ejecuta VACUUM para optimizar la base de datos"""
        try:
            async with self.get_connection() as db:
                await db.execute("VACUUM")
                
            self.logger.info("Base de datos optimizada con VACUUM")
            
        except Exception as e:
            self.error_logger.log_database_error("vacuum_database", e)
            raise
    
    async def backup_database(self, backup_path: Optional[Path] = None) -> Path:
        """Crea un backup de la base de datos"""
        try:
            if backup_path is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = self.db_path.parent / f"backup_{timestamp}.db"
            
            async with aiosqlite.connect(self.db_path) as source:
                async with aiosqlite.connect(backup_path) as backup:
                    await source.backup(backup)
            
            self.logger.info("Backup creado exitosamente", backup_path=str(backup_path))
            return backup_path
            
        except Exception as e:
            self.error_logger.log_database_error("backup_database", e)
            raise
    
    async def close(self) -> None:
        """Cierra la conexión a la base de datos"""
        self.logger.info("Cerrando conexión a la base de datos")
        # En aiosqlite no hay conexión persistente que cerrar
        pass


# Instancia global del gestor de base de datos
_database_manager = None


async def get_database_manager() -> DatabaseManager:
    """Obtiene la instancia global del gestor de base de datos"""
    global _database_manager
    if _database_manager is None:
        _database_manager = DatabaseManager()
        await _database_manager.initialize()
    return _database_manager


if __name__ == "__main__":
    # Test básico del database manager
    async def test_database():
        db = await get_database_manager()
        
        # Test estadísticas
        stats = await db.get_database_stats()
        print("Estadísticas de la base de datos:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
        
        # Test crear usuario
        user_data = {
            "employee_id": "EMP001",
            "document_id": "12345678",
            "name": "Usuario Test",
            "department": "IT",
            "company": "Test Corp"
        }
        
        try:
            user_id = await db.create_user(user_data)
            print(f"Usuario creado con ID: {user_id}")
            
            # Test buscar usuario
            found_user = await db.get_user_by_document_id("12345678")
            print(f"Usuario encontrado: {found_user['name']}")
            
        except Exception as e:
            print(f"Error (esperado si usuario ya existe): {e}")
        
        # Test crear registro
        record_data = {
            "user_id": 1,
            "document_id": "12345678",
            "employee_name": "Usuario Test",
            "access_timestamp": datetime.now().isoformat(),
            "method": "offline",
            "verification_type": "test",
            "device_id": "TERMINAL_001"
        }
        
        record_id = await db.create_access_record(record_data)
        print(f"Registro creado con ID: {record_id}")
        
        # Test estadísticas actualizadas
        stats = await db.get_database_stats()
        print("\nEstadísticas actualizadas:")
        for key, value in stats.items():
            print(f"  {key}: {value}")
    
    asyncio.run(test_database())
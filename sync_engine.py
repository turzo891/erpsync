"""
Bidirectional Sync Engine for ERP systems
"""
import json
import yaml
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from models import SyncRecord, SyncLog, ConflictRecord, get_db
from frappe_client import FrappeClient


class SyncEngine:
    """Handles bidirectional synchronization between two ERP instances"""

    def __init__(self, cloud_client: FrappeClient, local_client: FrappeClient, config_path: str = 'config.yaml'):
        """
        Initialize sync engine

        Args:
            cloud_client: FrappeClient for cloud ERP
            local_client: FrappeClient for local ERP
            config_path: Path to configuration file
        """
        self.cloud = cloud_client
        self.local = local_client

        # Load configuration
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)

        self.sync_rules = self.config.get('sync_rules', {})
        self.doctypes = self.sync_rules.get('doctypes', [])
        self.exclude_fields = self.sync_rules.get('exclude_fields', [])
        self.conflict_resolution = self.sync_rules.get('conflict_resolution', 'latest_timestamp')

    def sync_document(self, doctype: str, docname: str, direction: str = 'auto') -> Tuple[bool, str]:
        """
        Sync a single document

        Args:
            doctype: Document type
            docname: Document name/ID
            direction: 'cloud_to_local', 'local_to_cloud', or 'auto'

        Returns:
            Tuple of (success: bool, message: str)
        """
        db = get_db()
        try:
            # Get document from both systems
            cloud_doc = self.cloud.get_doc(doctype, docname)
            local_doc = self.local.get_doc(doctype, docname)

            # Get sync record
            sync_record = db.query(SyncRecord).filter_by(
                doctype=doctype,
                docname=docname
            ).first()

            if not sync_record:
                sync_record = SyncRecord(doctype=doctype, docname=docname)
                db.add(sync_record)

            # Prevent concurrent sync of same document
            if sync_record.is_syncing:
                return False, "Document is already being synced"

            sync_record.is_syncing = True
            db.commit()

            # Determine sync direction
            if direction == 'auto':
                direction = self._determine_sync_direction(cloud_doc, local_doc, sync_record)

            # Perform sync based on direction
            result, message = self._execute_sync(
                doctype, docname, cloud_doc, local_doc, direction, sync_record, db
            )

            # Update sync record
            sync_record.is_syncing = False
            sync_record.last_synced = datetime.utcnow()
            if result:
                sync_record.sync_status = 'synced'
                sync_record.retry_count = 0
            else:
                sync_record.sync_status = 'error'
                sync_record.error_message = message
                sync_record.retry_count += 1

            db.commit()

            # Log sync operation
            self._log_sync(db, doctype, docname, direction, result, message)

            return result, message

        except Exception as e:
            if sync_record:
                sync_record.is_syncing = False
                sync_record.sync_status = 'error'
                sync_record.error_message = str(e)
            db.commit()
            return False, f"Sync failed: {str(e)}"
        finally:
            db.close()

    def _determine_sync_direction(self, cloud_doc: Optional[Dict], local_doc: Optional[Dict],
                                   sync_record: SyncRecord) -> str:
        """
        Automatically determine sync direction based on document state

        Args:
            cloud_doc: Document from cloud ERP
            local_doc: Document from local ERP
            sync_record: Sync tracking record

        Returns:
            Sync direction string
        """
        # New document scenarios
        if cloud_doc and not local_doc:
            return 'cloud_to_local'
        if local_doc and not cloud_doc:
            return 'local_to_cloud'

        # Both exist - check modification times
        if cloud_doc and local_doc:
            cloud_modified = self._parse_datetime(cloud_doc.get('modified'))
            local_modified = self._parse_datetime(local_doc.get('modified'))

            # Calculate hashes to detect changes
            cloud_hash = FrappeClient.calculate_hash(cloud_doc, self.exclude_fields)
            local_hash = FrappeClient.calculate_hash(local_doc, self.exclude_fields)

            # No changes since last sync
            if (cloud_hash == sync_record.sync_hash_cloud and
                local_hash == sync_record.sync_hash_local):
                return 'none'

            # Cloud changed, local didn't
            if (cloud_hash != sync_record.sync_hash_cloud and
                local_hash == sync_record.sync_hash_local):
                return 'cloud_to_local'

            # Local changed, cloud didn't
            if (local_hash != sync_record.sync_hash_local and
                cloud_hash == sync_record.sync_hash_cloud):
                return 'local_to_cloud'

            # Both changed - CONFLICT!
            if (cloud_hash != sync_record.sync_hash_cloud and
                local_hash != sync_record.sync_hash_local):
                return 'conflict'

        return 'none'

    def _execute_sync(self, doctype: str, docname: str, cloud_doc: Optional[Dict],
                      local_doc: Optional[Dict], direction: str, sync_record: SyncRecord,
                      db: Session) -> Tuple[bool, str]:
        """
        Execute the actual sync operation

        Args:
            doctype: Document type
            docname: Document name
            cloud_doc: Cloud document data
            local_doc: Local document data
            direction: Sync direction
            sync_record: Sync record to update
            db: Database session

        Returns:
            Tuple of (success, message)
        """
        try:
            if direction == 'none':
                return True, "No changes to sync"

            elif direction == 'conflict':
                return self._handle_conflict(doctype, docname, cloud_doc, local_doc, sync_record, db)

            elif direction == 'cloud_to_local':
                if not cloud_doc:
                    # Document deleted on cloud, delete locally
                    if local_doc:
                        self.local.delete_doc(doctype, docname)
                        return True, "Deleted from local (deleted on cloud)"
                else:
                    # Create or update on local
                    cleaned_doc = self._clean_doc_for_sync(cloud_doc)

                    if local_doc:
                        # Update with automatic timestamp mismatch handling
                        self.local.update_doc(doctype, docname, cleaned_doc, retry_on_timestamp_mismatch=True)
                        sync_record.local_modified = datetime.utcnow()
                        sync_record.sync_hash_local = FrappeClient.calculate_hash(cleaned_doc, self.exclude_fields)
                        # Update cloud hash too since we just synced from cloud
                        sync_record.sync_hash_cloud = FrappeClient.calculate_hash(cloud_doc, self.exclude_fields)
                        sync_record.cloud_modified = self._parse_datetime(cloud_doc.get('modified'))
                        return True, "Updated on local from cloud"
                    else:
                        self.local.create_doc(doctype, cleaned_doc)
                        sync_record.local_modified = datetime.utcnow()
                        sync_record.sync_hash_local = FrappeClient.calculate_hash(cleaned_doc, self.exclude_fields)
                        sync_record.sync_hash_cloud = FrappeClient.calculate_hash(cloud_doc, self.exclude_fields)
                        sync_record.cloud_modified = self._parse_datetime(cloud_doc.get('modified'))
                        return True, "Created on local from cloud"

            elif direction == 'local_to_cloud':
                if not local_doc:
                    # Document deleted on local, delete on cloud
                    if cloud_doc:
                        self.cloud.delete_doc(doctype, docname)
                        return True, "Deleted from cloud (deleted on local)"
                else:
                    # Create or update on cloud
                    cleaned_doc = self._clean_doc_for_sync(local_doc)

                    if cloud_doc:
                        # Update with automatic timestamp mismatch handling
                        self.cloud.update_doc(doctype, docname, cleaned_doc, retry_on_timestamp_mismatch=True)
                        sync_record.cloud_modified = datetime.utcnow()
                        sync_record.sync_hash_cloud = FrappeClient.calculate_hash(cleaned_doc, self.exclude_fields)
                        # Update local hash too since we just synced from local
                        sync_record.sync_hash_local = FrappeClient.calculate_hash(local_doc, self.exclude_fields)
                        sync_record.local_modified = self._parse_datetime(local_doc.get('modified'))
                        return True, "Updated on cloud from local"
                    else:
                        self.cloud.create_doc(doctype, cleaned_doc)
                        sync_record.cloud_modified = datetime.utcnow()
                        sync_record.sync_hash_cloud = FrappeClient.calculate_hash(cleaned_doc, self.exclude_fields)
                        sync_record.sync_hash_local = FrappeClient.calculate_hash(local_doc, self.exclude_fields)
                        sync_record.local_modified = self._parse_datetime(local_doc.get('modified'))
                        return True, "Created on cloud from local"

            return False, f"Unknown sync direction: {direction}"

        except Exception as e:
            return False, f"Sync execution failed: {str(e)}"

    def _handle_conflict(self, doctype: str, docname: str, cloud_doc: Dict, local_doc: Dict,
                        sync_record: SyncRecord, db: Session) -> Tuple[bool, str]:
        """
        Handle sync conflicts using configured resolution strategy

        Args:
            doctype: Document type
            docname: Document name
            cloud_doc: Cloud document
            local_doc: Local document
            sync_record: Sync record
            db: Database session

        Returns:
            Tuple of (success, message)
        """
        # Record the conflict
        conflict = ConflictRecord(
            doctype=doctype,
            docname=docname,
            cloud_data=json.dumps(cloud_doc, default=str),
            local_data=json.dumps(local_doc, default=str),
            cloud_modified=self._parse_datetime(cloud_doc.get('modified')),
            local_modified=self._parse_datetime(local_doc.get('modified'))
        )
        db.add(conflict)

        # Apply resolution strategy
        strategy = self.conflict_resolution

        if strategy == 'latest_timestamp':
            cloud_time = self._parse_datetime(cloud_doc.get('modified'))
            local_time = self._parse_datetime(local_doc.get('modified'))

            if cloud_time > local_time:
                direction = 'cloud_to_local'
                resolution = 'cloud_wins (latest)'
            else:
                direction = 'local_to_cloud'
                resolution = 'local_wins (latest)'

        elif strategy == 'cloud_wins':
            direction = 'cloud_to_local'
            resolution = 'cloud_wins'

        elif strategy == 'local_wins':
            direction = 'local_to_cloud'
            resolution = 'local_wins'

        elif strategy == 'manual':
            sync_record.sync_status = 'conflict'
            return False, "Conflict detected - manual resolution required"

        else:
            return False, f"Unknown conflict resolution strategy: {strategy}"

        # Mark conflict as resolved
        conflict.resolved = True
        conflict.resolution = resolution
        conflict.resolved_at = datetime.utcnow()

        # Execute sync with chosen direction
        result, message = self._execute_sync(
            doctype, docname, cloud_doc, local_doc, direction, sync_record, db
        )

        return result, f"Conflict resolved ({resolution}): {message}"

    def _clean_doc_for_sync(self, doc: Dict) -> Dict:
        """
        Clean document data before syncing (remove system fields)

        Args:
            doc: Original document

        Returns:
            Cleaned document
        """
        cleaned = doc.copy()

        # Remove fields that should not be synced
        fields_to_remove = [
            'name',  # Will be set by target system
            'owner',
            'modified_by',
            'creation',
            'modified',
            'docstatus',
            '_user_tags',
            '_comments',
            '_assign',
            '_liked_by'
        ] + self.exclude_fields

        for field in fields_to_remove:
            cleaned.pop(field, None)

        return cleaned

    def _parse_datetime(self, dt_str: str) -> datetime:
        """Parse datetime string from Frappe"""
        if not dt_str:
            return datetime.min

        try:
            return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S.%f')
        except ValueError:
            try:
                return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')
            except ValueError:
                return datetime.min

    def _log_sync(self, db: Session, doctype: str, docname: str, direction: str,
                  success: bool, message: str):
        """Log sync operation"""
        log = SyncLog(
            doctype=doctype,
            docname=docname,
            action='sync',
            direction=direction,
            status='success' if success else 'failed',
            message=message
        )
        db.add(log)
        db.commit()

    def sync_all_doctypes(self, limit: int = 100) -> Dict[str, int]:
        """
        Sync all configured doctypes

        Args:
            limit: Maximum documents per doctype to sync

        Returns:
            Dictionary with sync statistics
        """
        stats = {
            'total': 0,
            'success': 0,
            'failed': 0,
            'conflicts': 0,
            'skipped': 0
        }

        print(f"\nSYNC: Starting full sync for {len(self.doctypes)} DocTypes...\n")

        for doctype in self.doctypes:
            print(f"Syncing {doctype}...")
            doctype_stats = self.sync_doctype(doctype, limit)

            stats['total'] += doctype_stats['total']
            stats['success'] += doctype_stats['success']
            stats['failed'] += doctype_stats['failed']
            stats['conflicts'] += doctype_stats['conflicts']
            stats['skipped'] += doctype_stats['skipped']

        print(f"\nSUCCESS: Sync completed!")
        print(f"Total: {stats['total']}, Success: {stats['success']}, "
              f"Failed: {stats['failed']}, Conflicts: {stats['conflicts']}, "
              f"Skipped: {stats['skipped']}\n")

        return stats

    def sync_doctype(self, doctype: str, limit: int = 100) -> Dict[str, int]:
        """
        Sync all documents of a specific doctype

        Args:
            doctype: Document type to sync
            limit: Maximum documents to sync

        Returns:
            Dictionary with sync statistics
        """
        stats = {'total': 0, 'success': 0, 'failed': 0, 'conflicts': 0, 'skipped': 0}

        try:
            # Get all documents from both systems
            cloud_docs = self.cloud.get_list(doctype, limit_page_length=limit)
            local_docs = self.local.get_list(doctype, limit_page_length=limit)

            # Create sets of document names
            cloud_names = {doc.get('name') for doc in cloud_docs}
            local_names = {doc.get('name') for doc in local_docs}
            all_names = cloud_names.union(local_names)

            stats['total'] = len(all_names)

            # Sync each document
            for docname in all_names:
                success, message = self.sync_document(doctype, docname)

                if success:
                    if 'conflict' in message.lower():
                        stats['conflicts'] += 1
                    else:
                        stats['success'] += 1
                elif 'no changes' in message.lower():
                    stats['skipped'] += 1
                else:
                    stats['failed'] += 1
                    print(f"  [FAIL] {docname}: {message}")

        except Exception as e:
            print(f"Error syncing {doctype}: {e}")
            stats['failed'] += 1

        return stats


if __name__ == '__main__':
    # Test sync engine
    import os
    from dotenv import load_dotenv

    load_dotenv()

    cloud = FrappeClient(
        url=os.getenv('CLOUD_ERP_URL'),
        api_key=os.getenv('CLOUD_API_KEY'),
        api_secret=os.getenv('CLOUD_API_SECRET'),
        instance_name='Cloud'
    )

    local = FrappeClient(
        url=os.getenv('LOCAL_ERP_URL'),
        api_key=os.getenv('LOCAL_API_KEY'),
        api_secret=os.getenv('LOCAL_API_SECRET'),
        instance_name='Local'
    )

    engine = SyncEngine(cloud, local)
    print("Sync engine initialized")

"""
Frappe API Client for communicating with ERP systems
"""
import requests
import json
from typing import Dict, List, Optional, Any
from datetime import datetime
import hashlib


class FrappeClient:
    """Client for Frappe/ERPNext API"""

    def __init__(self, url: str, api_key: str, api_secret: str, instance_name: str = ""):
        """
        Initialize Frappe API client

        Args:
            url: Base URL of Frappe instance (e.g., https://erp.example.com)
            api_key: API key for authentication
            api_secret: API secret for authentication
            instance_name: Name for this instance (cloud/local)
        """
        self.url = url.rstrip('/')
        self.api_key = api_key
        self.api_secret = api_secret
        self.instance_name = instance_name
        self.session = requests.Session()
        self.session.headers.update({
            'Authorization': f'token {api_key}:{api_secret}',
            'Content-Type': 'application/json'
        })

    def get_doc(self, doctype: str, docname: str) -> Optional[Dict]:
        """
        Get a document from Frappe

        Args:
            doctype: Document type (e.g., 'Customer')
            docname: Document name/ID

        Returns:
            Document data as dictionary or None if not found
        """
        try:
            url = f'{self.url}/api/resource/{doctype}/{docname}'
            response = self.session.get(url)
            response.raise_for_status()
            return response.json().get('data')
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                return None
            raise
        except Exception as e:
            print(f"Error getting doc {doctype}/{docname}: {e}")
            raise

    def get_list(self, doctype: str, filters: Optional[Dict] = None,
                 fields: Optional[List[str]] = None,
                 limit_start: int = 0, limit_page_length: int = 20) -> List[Dict]:
        """
        Get list of documents

        Args:
            doctype: Document type
            filters: Filter conditions
            fields: Fields to retrieve
            limit_start: Starting offset
            limit_page_length: Number of records to retrieve

        Returns:
            List of documents
        """
        try:
            url = f'{self.url}/api/resource/{doctype}'
            params = {
                'limit_start': limit_start,
                'limit_page_length': limit_page_length
            }

            if filters:
                params['filters'] = json.dumps(filters)
            if fields:
                params['fields'] = json.dumps(fields)

            response = self.session.get(url, params=params)
            response.raise_for_status()
            return response.json().get('data', [])
        except Exception as e:
            print(f"Error getting list for {doctype}: {e}")
            raise

    def create_doc(self, doctype: str, doc_data: Dict) -> Dict:
        """
        Create a new document

        Args:
            doctype: Document type
            doc_data: Document data

        Returns:
            Created document data
        """
        try:
            url = f'{self.url}/api/resource/{doctype}'
            doc_data['doctype'] = doctype

            response = self.session.post(url, json=doc_data)
            response.raise_for_status()
            return response.json().get('data')
        except Exception as e:
            print(f"Error creating doc {doctype}: {e}")
            raise

    def update_doc(self, doctype: str, docname: str, doc_data: Dict, retry_on_timestamp_mismatch: bool = True) -> Dict:
        """
        Update an existing document

        Args:
            doctype: Document type
            docname: Document name/ID
            doc_data: Updated document data
            retry_on_timestamp_mismatch: If True, automatically retry on timestamp mismatch

        Returns:
            Updated document data
        """
        max_retries = 3
        retry_count = 0

        while retry_count < max_retries:
            try:
                url = f'{self.url}/api/resource/{doctype}/{docname}'

                # If retrying, get the latest document first to get current timestamp
                if retry_count > 0 and retry_on_timestamp_mismatch:
                    print(f"  RETRY: Retry {retry_count}/{max_retries}: Fetching latest version of {doctype}/{docname}")
                    latest_doc = self.get_doc(doctype, docname)
                    if latest_doc:
                        # Preserve the current modified timestamp for the update
                        doc_data['modified'] = latest_doc.get('modified')

                response = self.session.put(url, json=doc_data)
                response.raise_for_status()
                return response.json().get('data')

            except requests.exceptions.HTTPError as e:
                error_message = str(e)

                # Check if it's a timestamp mismatch error
                if e.response is not None:
                    try:
                        error_data = e.response.json()
                        error_message = error_data.get('_server_messages', '') or error_data.get('message', str(e))
                    except:
                        error_message = e.response.text or str(e)

                # Frappe timestamp mismatch errors contain specific text
                is_timestamp_error = any(keyword in error_message.lower() for keyword in [
                    'timestamp mismatch',
                    'document has been modified',
                    'has been modified after you have opened it'
                ])

                if is_timestamp_error and retry_on_timestamp_mismatch and retry_count < max_retries - 1:
                    retry_count += 1
                    print(f"  WARNING: Timestamp mismatch detected for {doctype}/{docname}, retrying...")
                    continue
                else:
                    print(f"Error updating doc {doctype}/{docname}: {error_message}")
                    raise

            except Exception as e:
                print(f"Error updating doc {doctype}/{docname}: {e}")
                raise

        raise Exception(f"Failed to update {doctype}/{docname} after {max_retries} retries due to timestamp mismatch")

    def delete_doc(self, doctype: str, docname: str) -> bool:
        """
        Delete a document

        Args:
            doctype: Document type
            docname: Document name/ID

        Returns:
            True if successful
        """
        try:
            url = f'{self.url}/api/resource/{doctype}/{docname}'
            response = self.session.delete(url)
            response.raise_for_status()
            return True
        except Exception as e:
            print(f"Error deleting doc {doctype}/{docname}: {e}")
            raise

    def get_modified_docs(self, doctype: str, modified_after: datetime,
                          limit: int = 100) -> List[Dict]:
        """
        Get documents modified after a specific timestamp

        Args:
            doctype: Document type
            modified_after: Get docs modified after this datetime
            limit: Maximum number of documents to retrieve

        Returns:
            List of modified documents
        """
        try:
            modified_str = modified_after.strftime('%Y-%m-%d %H:%M:%S')
            filters = {
                'modified': ['>', modified_str]
            }

            return self.get_list(
                doctype,
                filters=filters,
                limit_page_length=limit
            )
        except Exception as e:
            print(f"Error getting modified docs for {doctype}: {e}")
            raise

    def install_webhook(self, doctype: str, webhook_url: str, secret: str) -> bool:
        """
        Install webhook for a doctype (requires manual setup in Frappe)

        This is a helper method that provides instructions.
        Webhooks must be configured in Frappe UI.

        Args:
            doctype: Document type to monitor
            webhook_url: URL to send webhook events
            secret: Secret key for webhook validation

        Returns:
            Instructions string
        """
        instructions = f"""
        To set up webhook in Frappe/ERPNext:

        1. Login to {self.url}
        2. Go to: Setup > Integrations > Webhook
        3. Create New Webhook with:
           - Document Type: {doctype}
           - Request URL: {webhook_url}
           - Webhook Secret: {secret}
           - Enable: After Insert, After Save, After Delete
           - Condition: (leave blank for all documents)

        4. Save the webhook

        Repeat for all DocTypes you want to sync.
        """
        print(instructions)
        return True

    @staticmethod
    def calculate_hash(doc_data: Dict, exclude_fields: List[str] = None) -> str:
        """
        Calculate MD5 hash of document data for change detection

        Args:
            doc_data: Document data
            exclude_fields: Fields to exclude from hash calculation

        Returns:
            MD5 hash string
        """
        if exclude_fields is None:
            exclude_fields = ['modified', 'modified_by', 'creation', 'owner', 'idx']

        # Create a clean copy without excluded fields
        clean_data = {k: v for k, v in doc_data.items() if k not in exclude_fields}

        # Sort keys for consistent hashing
        json_str = json.dumps(clean_data, sort_keys=True, default=str)
        return hashlib.md5(json_str.encode()).hexdigest()

    def test_connection(self) -> bool:
        """
        Test connection to Frappe instance

        Returns:
            True if connection successful
        """
        try:
            url = f'{self.url}/api/method/frappe.auth.get_logged_user'
            response = self.session.get(url)
            response.raise_for_status()
            user = response.json().get('message')
            print(f"[OK] Connected to {self.instance_name} ({self.url}) as user: {user}")
            return True
        except Exception as e:
            print(f"[FAIL] Failed to connect to {self.instance_name} ({self.url}): {e}")
            return False


if __name__ == '__main__':
    # Test the client
    import os
    from dotenv import load_dotenv

    load_dotenv()

    # Test cloud connection
    cloud_client = FrappeClient(
        url=os.getenv('CLOUD_ERP_URL'),
        api_key=os.getenv('CLOUD_API_KEY'),
        api_secret=os.getenv('CLOUD_API_SECRET'),
        instance_name='Cloud'
    )
    cloud_client.test_connection()

    # Test local connection
    local_client = FrappeClient(
        url=os.getenv('LOCAL_ERP_URL'),
        api_key=os.getenv('LOCAL_API_KEY'),
        api_secret=os.getenv('LOCAL_API_SECRET'),
        instance_name='Local'
    )
    local_client.test_connection()

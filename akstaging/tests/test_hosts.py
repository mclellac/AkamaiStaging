import unittest
from unittest.mock import patch, mock_open, MagicMock, call
import os
import shutil # For tests that might involve shutil, though we'll mock it mostly
from datetime import datetime

# Attempt to import HostsFileEdit from the correct location
# This assumes your project structure allows this import from the test directory
try:
    from akstaging.hosts import HostsFileEdit
    from akstaging.aklib import AkamaiLib # For mocking print_to_textview if it's a class method
except ImportError:
    # This is a fallback if the direct import fails,
    # you might need to adjust sys.path if running tests directly and not via a test runner
    # For example, by adding the parent directory of 'akstaging' to sys.path
    import sys
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
    from akstaging.hosts import HostsFileEdit
    from akstaging.aklib import AkamaiLib


class TestHostsFileEdit(unittest.TestCase):

    def setUp(self):
        self.hfe = HostsFileEdit()

        # 1. Mock HOSTS_FILE path
        self.mock_hosts_file_path = '/mocked/etc/hosts'
        self.hosts_file_patch = patch.object(HostsFileEdit, 'HOSTS_FILE', self.mock_hosts_file_path)
        self.hosts_file_patch.start()

        # Standard initial hosts content for many tests (can be removed if no old tests use it)
        self.initial_hosts_content = "127.0.0.1 localhost\n1.1.1.1 example.com\n2.2.2.2 another.com"

    def tearDown(self):
        self.hosts_file_patch.stop()
        # Ensure any other patches started directly in tests are stopped.
        patch.stopall() # Stops all patches started with start()

    # --- Tests for get_existing_ip_for_domain ---

    @patch('builtins.open', new_callable=mock_open)
    def test_get_existing_ip_for_domain_found(self, mock_file):
        mock_file.return_value.read.return_value = self.initial_hosts_content
        mock_file.return_value.__enter__.return_value.readlines.return_value = self.initial_hosts_content.splitlines(True)
        mock_file.return_value.__iter__.return_value = self.initial_hosts_content.splitlines(True)

        ip = self.hfe.get_existing_ip_for_domain("example.com")
        self.assertEqual(ip, "1.1.1.1")
        mock_file.assert_called_once_with(self.mock_hosts_file_path, "r", encoding="utf-8")

    @patch('builtins.open', new_callable=mock_open)
    def test_get_existing_ip_for_domain_not_found(self, mock_file):
        mock_file.return_value.read.return_value = self.initial_hosts_content
        mock_file.return_value.__enter__.return_value.readlines.return_value = self.initial_hosts_content.splitlines(True)
        mock_file.return_value.__iter__.return_value = self.initial_hosts_content.splitlines(True)
        
        ip = self.hfe.get_existing_ip_for_domain("nonexistent.com")
        self.assertIsNone(ip)
        mock_file.assert_called_once_with(self.mock_hosts_file_path, "r", encoding="utf-8")

    @patch('builtins.open', side_effect=FileNotFoundError("File not found"))
    def test_get_existing_ip_for_domain_hosts_file_not_found(self, mock_open_call):
        with self.assertRaises(FileNotFoundError) as context:
            self.hfe.get_existing_ip_for_domain("example.com")
        self.assertIn(f"Error reading {self.mock_hosts_file_path}", str(context.exception))
        mock_open_call.assert_called_once_with(self.mock_hosts_file_path, "r", encoding="utf-8")

    @patch('builtins.open', side_effect=PermissionError("Permission denied"))
    def test_get_existing_ip_for_domain_hosts_permission_error(self, mock_open_call):
        with self.assertRaises(PermissionError) as context:
            self.hfe.get_existing_ip_for_domain("example.com")
        self.assertIn(f"Permission denied when trying to read {self.mock_hosts_file_path}", str(context.exception))
        mock_open_call.assert_called_once_with(self.mock_hosts_file_path, "r", encoding="utf-8")

    @patch('builtins.open', new_callable=mock_open)
    def test_get_existing_ip_for_domain_handles_line_splitting_correctly(self, mock_file):
        # Test for lines with multiple spaces or tabs, and various hostnames
        hosts_content_complex = (
            "127.0.0.1  localhost\n"
            "# This is a comment\n"
            "\n" # Empty line
            "1.1.1.1\texample.com\talias.example.com\n"
            "2.2.2.2 another.com # Inline comment\n"
            "3.3.3.3 third.com fourth.com" # Multiple hostnames
        )
        mock_file.return_value.read.return_value = hosts_content_complex
        mock_file.return_value.__enter__.return_value.readlines.return_value = hosts_content_complex.splitlines(True)
        mock_file.return_value.__iter__.return_value = hosts_content_complex.splitlines(True)

        self.assertEqual(self.hfe.get_existing_ip_for_domain("example.com"), "1.1.1.1")
        # The current get_existing_ip_for_domain implementation only checks the first hostname after IP.
        # If it were to check all hostnames on a line, this test would need adjustment.
        # For "1.1.1.1 example.com alias.example.com", it would find "example.com" if it's the "canonical" one.
        # The code is: `hostname = " ".join(line_parts[1:])`. So it matches the full string of hostnames.
        # This means it would NOT find "alias.example.com" unless it was the only one.
        # The current code `if hostname == sanitized_domain:` implies `sanitized_domain` must be the complete hostname part.
        # This is a limitation of the current `get_existing_ip_for_domain`. For now, the test reflects this.
        # If `sanitized_domain` is "example.com alias.example.com", it should find it.
        self.assertEqual(self.hfe.get_existing_ip_for_domain("example.com alias.example.com"), "1.1.1.1")
        self.assertEqual(self.hfe.get_existing_ip_for_domain("another.com"), "2.2.2.2") # Assuming inline comments are stripped by split()
        self.assertEqual(self.hfe.get_existing_ip_for_domain("third.com fourth.com"), "3.3.3.3")
        self.assertIsNone(self.hfe.get_existing_ip_for_domain("alias.example.com")) # Due to current implementation detail
        self.assertIsNone(self.hfe.get_existing_ip_for_domain("localhost # some comment"))

    # --- Tests for create_backup ---

    @patch('akstaging.hosts.shutil.copy2')
    @patch('akstaging.hosts.os.makedirs')
    @patch('akstaging.hosts.datetime')
    def test_create_backup_success(self, mock_datetime, mock_makedirs, mock_copy2):
        # Setup mock datetime
        mock_now = MagicMock()
        mock_datetime.now.return_value = mock_now
        mock_now.strftime.return_value = "20230101_120000"

        expected_backup_filename = "hosts_backup_20230101_120000.txt"
        expected_backup_filepath = os.path.join(self.mock_backup_dir_path, expected_backup_filename)

        backup_path = self.hfe.create_backup()

        # Assertions
        mock_makedirs.assert_called_once_with(self.mock_backup_dir_path, exist_ok=True)
        mock_copy2.assert_called_once_with(self.mock_hosts_file_path, expected_backup_filepath)
        self.assertEqual(backup_path, expected_backup_filepath)
        mock_datetime.now.assert_called_once()
        mock_now.strftime.assert_called_once_with("%Y%m%d_%H%M%S")

    @patch('akstaging.hosts.os.makedirs', side_effect=OSError("Permission denied creating dir"))
    def test_create_backup_makedirs_os_error(self, mock_makedirs):
        with self.assertRaises(IOError) as context:
            self.hfe.create_backup()
        self.assertIn(f"Error creating backup directory {self.mock_backup_dir_path}", str(context.exception))
        mock_makedirs.assert_called_once_with(self.mock_backup_dir_path, exist_ok=True)

    @patch('akstaging.hosts.shutil.copy2', side_effect=PermissionError("Permission denied copying file"))
    @patch('akstaging.hosts.os.makedirs') # Mock makedirs to prevent it from erroring
    def test_create_backup_copy_permission_error(self, mock_makedirs, mock_copy2):
        with self.assertRaises(PermissionError) as context:
            self.hfe.create_backup()
        self.assertIn("Permission denied when trying to read", str(context.exception))
        mock_copy2.assert_called_once() # Check that copy2 was attempted

    @patch('akstaging.hosts.shutil.copy2', side_effect=FileNotFoundError("Source file not found"))
    @patch('akstaging.hosts.os.makedirs')
    def test_create_backup_copy_source_not_found_error(self, mock_makedirs, mock_copy2):
        with self.assertRaises(FileNotFoundError) as context:
            self.hfe.create_backup()
        self.assertIn(f"Error backing up {self.mock_hosts_file_path}: Source file not found", str(context.exception))
        mock_copy2.assert_called_once()

    @patch('akstaging.hosts.shutil.copy2', side_effect=OSError("Some other OS error during copy"))
    @patch('akstaging.hosts.os.makedirs')
    def test_create_backup_copy_os_error(self, mock_makedirs, mock_copy2):
        with self.assertRaises(IOError) as context:
            self.hfe.create_backup()
        self.assertIn(f"Error copying {self.mock_hosts_file_path}", str(context.exception)) # Part of the message
        mock_copy2.assert_called_once()

    # --- Tests for list_backups ---

    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch('akstaging.hosts.os.listdir', return_value=[])
    def test_list_backups_empty_directory(self, mock_listdir, mock_isdir):
        backups = self.hfe.list_backups()
        self.assertEqual(backups, [])
        mock_isdir.assert_called_once_with(self.mock_backup_dir_path)
        mock_listdir.assert_called_once_with(self.mock_backup_dir_path)

    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch('akstaging.hosts.os.path.isfile')
    @patch('akstaging.hosts.os.listdir')
    def test_list_backups_multiple_files_sorted(self, mock_listdir, mock_isfile, mock_isdir):
        # Mock os.listdir to return a list of filenames
        mock_listdir.return_value = [
            "hosts_backup_20230101_100000.txt",
            "hosts_backup_20230101_120000.txt", # newest
            "hosts_backup_20221231_230000.txt", # oldest
            "not_a_backup.txt",
            "hosts_backup_invalid_format.txt" # This one will be filtered by isfile or parsing
        ]
        # Mock os.path.isfile to return True for valid backup files
        def isfile_side_effect(path):
            filename = os.path.basename(path)
            if filename in ["hosts_backup_20230101_100000.txt", "hosts_backup_20230101_120000.txt", "hosts_backup_20221231_230000.txt"]:
                return True
            if filename == "hosts_backup_invalid_format.txt": # Simulate it's a file, but parsing will fail
                return True
            return False
        mock_isfile.side_effect = isfile_side_effect
        
        # Expected order: newest to oldest
        expected_backups = [
            "hosts_backup_20230101_120000.txt",
            "hosts_backup_20230101_100000.txt",
            "hosts_backup_20221231_230000.txt",
        ]
        
        # Patch datetime.strptime to handle the valid ones, and raise ValueError for the invalid one
        original_strptime = datetime.strptime
        def strptime_side_effect(date_string, format_string):
            if date_string == "invalid_format":
                raise ValueError("Invalid date format for test")
            return original_strptime(date_string, format_string)

        with patch('akstaging.hosts.datetime.strptime', side_effect=strptime_side_effect) as mock_strptime:
            backups = self.hfe.list_backups()

        self.assertEqual(backups, expected_backups)
        mock_isdir.assert_called_once_with(self.mock_backup_dir_path)
        mock_listdir.assert_called_once_with(self.mock_backup_dir_path)
        # Check that isfile was called for each file returned by listdir
        self.assertEqual(mock_isfile.call_count, 5)


    @patch('akstaging.hosts.os.path.isdir', return_value=False)
    def test_list_backups_non_existent_directory(self, mock_isdir):
        backups = self.hfe.list_backups()
        self.assertEqual(backups, [])
        mock_isdir.assert_called_once_with(self.mock_backup_dir_path)

    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch('akstaging.hosts.os.listdir', side_effect=OSError("Permission denied listing files"))
    def test_list_backups_listdir_os_error(self, mock_listdir, mock_isdir):
        backups = self.hfe.list_backups()
        # As per implementation, it should return an empty list on OSError
        self.assertEqual(backups, [])
        mock_isdir.assert_called_once_with(self.mock_backup_dir_path)
        mock_listdir.assert_called_once_with(self.mock_backup_dir_path)

    # --- Tests for restore_backup ---

    @patch('akstaging.hosts.shutil.copy2')
    @patch.object(HostsFileEdit, 'create_backup') # Mocking the instance method directly
    @patch.object(HostsFileEdit, 'list_backups')
    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch('akstaging.hosts.os.path.isfile', return_value=True) # Assume specified backup file exists
    def test_restore_backup_specific_file(self, mock_os_isfile, mock_os_isdir, mock_list_backups, mock_hfe_create_backup, mock_shutil_copy2):
        backup_to_restore = "hosts_backup_20230101_110000.txt"
        full_backup_path = os.path.join(self.mock_backup_dir_path, backup_to_restore)
        mock_hfe_create_backup.return_value = "/mocked/pre_restore_backup.txt" # Path of the pre-restore backup

        result = self.hfe.restore_backup(backup_to_restore)

        self.assertTrue(result)
        mock_os_isdir.assert_called_once_with(self.mock_backup_dir_path)
        mock_os_isfile.assert_called_once_with(full_backup_path)
        mock_hfe_create_backup.assert_called_once() # Ensure pre-restore backup was made
        mock_shutil_copy2.assert_called_once_with(full_backup_path, self.mock_hosts_file_path)
        mock_list_backups.assert_not_called() # Should not be called if filename is provided

    @patch('akstaging.hosts.shutil.copy2')
    @patch.object(HostsFileEdit, 'create_backup')
    @patch.object(HostsFileEdit, 'list_backups')
    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch('akstaging.hosts.os.path.isfile', return_value=True) # Assume newest backup file exists
    def test_restore_backup_most_recent(self, mock_os_isfile, mock_os_isdir, mock_list_backups, mock_hfe_create_backup, mock_shutil_copy2):
        # list_backups returns sorted list, newest first
        newest_backup_filename = "hosts_backup_20230102_120000.txt"
        mock_list_backups.return_value = [newest_backup_filename, "hosts_backup_20230101_100000.txt"]
        full_newest_backup_path = os.path.join(self.mock_backup_dir_path, newest_backup_filename)
        mock_hfe_create_backup.return_value = "/mocked/pre_restore_backup.txt"

        result = self.hfe.restore_backup() # No filename provided

        self.assertTrue(result)
        mock_os_isdir.assert_called_once_with(self.mock_backup_dir_path)
        mock_list_backups.assert_called_once()
        mock_hfe_create_backup.assert_called_once()
        mock_shutil_copy2.assert_called_once_with(full_newest_backup_path, self.mock_hosts_file_path)
        # os.path.isfile will be called internally by restore_backup to check the chosen backup's existence
        # This check might be redundant if list_backups is trusted, but good for robustness
        mock_os_isfile.assert_any_call(full_newest_backup_path)


    @patch('akstaging.hosts.os.path.isdir', return_value=False)
    def test_restore_backup_backup_dir_not_found(self, mock_os_isdir):
        with self.assertRaises(FileNotFoundError) as context:
            self.hfe.restore_backup("any_backup.txt")
        self.assertIn(f"Backup directory {self.mock_backup_dir_path} not found", str(context.exception))

    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch('akstaging.hosts.os.path.isfile', return_value=False)
    def test_restore_backup_specific_file_not_found(self, mock_os_isfile, mock_os_isdir):
        backup_to_restore = "non_existent_backup.txt"
        full_backup_path = os.path.join(self.mock_backup_dir_path, backup_to_restore)
        with self.assertRaises(FileNotFoundError) as context:
            self.hfe.restore_backup(backup_to_restore)
        self.assertIn(f"Specified backup file {full_backup_path} not found", str(context.exception))

    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch.object(HostsFileEdit, 'list_backups', return_value=[]) # No backups available
    def test_restore_backup_no_backups_available_for_most_recent(self, mock_list_backups, mock_os_isdir):
        with self.assertRaises(FileNotFoundError) as context:
            self.hfe.restore_backup() # No filename, tries most recent
        self.assertIn("No backups available to restore", str(context.exception))

    @patch.object(HostsFileEdit, 'create_backup', side_effect=IOError("Failed to create pre-restore backup"))
    @patch.object(HostsFileEdit, 'list_backups', return_value=["hosts_backup_20230102_120000.txt"])
    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch('akstaging.hosts.os.path.isfile', return_value=True)
    def test_restore_backup_pre_restore_backup_fails(self, mock_isfile, mock_isdir, mock_list_backups, mock_hfe_create_backup):
        with self.assertRaises(IOError) as context:
            self.hfe.restore_backup()
        self.assertIn(f"Failed to create a pre-restore backup of {self.mock_hosts_file_path}", str(context.exception))
        mock_hfe_create_backup.assert_called_once() # Ensure it was attempted

    @patch('akstaging.hosts.shutil.copy2', side_effect=PermissionError("Permission denied writing to hosts"))
    @patch.object(HostsFileEdit, 'create_backup', return_value="/mocked/pre_restore_backup.txt")
    @patch.object(HostsFileEdit, 'list_backups', return_value=["hosts_backup_20230102_120000.txt"])
    @patch('akstaging.hosts.os.path.isdir', return_value=True)
    @patch('akstaging.hosts.os.path.isfile', return_value=True)
    def test_restore_backup_permission_error_on_final_copy(self, mock_isfile, mock_isdir, mock_list_backups, mock_hfe_create_backup, mock_shutil_copy2):
        with self.assertRaises(PermissionError) as context:
            self.hfe.restore_backup()
        self.assertIn(f"Permission denied when trying to write to {self.mock_hosts_file_path}", str(context.exception))
        mock_hfe_create_backup.assert_called_once()
        mock_shutil_copy2.assert_called_once()

    # --- Tests for remove_hosts_entry ---

    @patch('builtins.open', new_callable=mock_open)
    @patch.object(HostsFileEdit, 'create_backup')
    def test_remove_hosts_entry_existing(self, mock_hfe_create_backup, mock_file):
        initial_content = "1.1.1.1 example.com\n2.2.2.2 another.com\n"
        # Configure the mock_open to handle read and write
        mock_file.return_value.__enter__.return_value.readlines.return_value = initial_content.splitlines(True)
        
        entry_to_remove = "1.1.1.1 example.com"
        expected_message = f"Removed /etc/hosts entry: {entry_to_remove}"
        
        message = self.hfe.remove_hosts_entry(entry_to_remove)
        
        self.assertEqual(message, expected_message)
        mock_hfe_create_backup.assert_called_once() # Backup should be called
        
        # Check that open was called for reading then for writing
        mock_file.assert_any_call(self.mock_hosts_file_path, "r", encoding="utf-8")
        mock_file.assert_any_call(self.mock_hosts_file_path, "w", encoding="utf-8")
        
        # Verify the content written to the file
        # The handle for the write call is the second one in mock_file.mock_calls
        # (index 2 because 0 is read, 1 is __enter__ for read, 2 could be write or readlines, need to be careful)
        # A more robust way: check the calls to write on the handle used for 'w'
        handle = mock_file()
        written_content = "".join(call_args[0][0] for call_args in handle.writelines.call_args_list)
        self.assertEqual(written_content, "2.2.2.2 another.com\n")


    @patch('builtins.open', new_callable=mock_open)
    @patch.object(HostsFileEdit, 'create_backup')
    def test_remove_hosts_entry_non_existing(self, mock_hfe_create_backup, mock_file):
        initial_content = "1.1.1.1 example.com\n"
        mock_file.return_value.__enter__.return_value.readlines.return_value = initial_content.splitlines(True)
        
        entry_to_remove = "3.3.3.3 nonexistent.com"
        expected_message = f"Entry '{entry_to_remove}' not found in {self.mock_hosts_file_path}. No changes made."
        
        message = self.hfe.remove_hosts_entry(entry_to_remove)
        
        self.assertEqual(message, expected_message)
        mock_hfe_create_backup.assert_not_called() # Backup should NOT be called
        mock_file.assert_called_once_with(self.mock_hosts_file_path, "r", encoding="utf-8")
        # Ensure no write call was made
        handle = mock_file()
        handle.writelines.assert_not_called()

    @patch('builtins.open', new_callable=mock_open, read_data="1.1.1.1 example.com\n")
    @patch.object(HostsFileEdit, 'create_backup', side_effect=PermissionError("Backup permission error"))
    def test_remove_hosts_entry_backup_fails_permission_error(self, mock_hfe_create_backup, mock_file):
        # Configure readlines for the initial read
        mock_file.return_value.__enter__.return_value.readlines.return_value = ["1.1.1.1 example.com\n", "2.2.2.2 other.com\n"]
        entry_to_remove = "1.1.1.1 example.com"
        with self.assertRaises(PermissionError) as context:
            self.hfe.remove_hosts_entry(entry_to_remove)
        self.assertIn("Backup permission error", str(context.exception))
        mock_hfe_create_backup.assert_called_once()
        # Ensure write was not attempted
        handle = mock_file()
        handle.writelines.assert_not_called()


    @patch('builtins.open', new_callable=mock_open)
    def test_remove_hosts_entry_write_permission_error(self, mock_file):
        initial_content = "1.1.1.1 example.com\n"
        mock_file.return_value.__enter__.return_value.readlines.return_value = initial_content.splitlines(True)
        # Simulate PermissionError on the write call
        mock_file.side_effect = [
            mock_open(read_data=initial_content).return_value, # For the read
            PermissionError("Permission denied writing") # For the write
        ]
        
        entry_to_remove = "1.1.1.1 example.com"
        # We need to mock create_backup here as well, otherwise it might fail first if not mocked.
        with patch.object(HostsFileEdit, 'create_backup') as mock_hfe_create_backup:
            with self.assertRaises(PermissionError) as context:
                self.hfe.remove_hosts_entry(entry_to_remove)
            self.assertIn("Permission denied during operation", str(context.exception)) # From hosts.py
            mock_hfe_create_backup.assert_called_once() # Backup is attempted before write

    @patch('builtins.open', side_effect=FileNotFoundError("Hosts file not found for read"))
    def test_remove_hosts_entry_read_file_not_found(self, mock_file):
        with self.assertRaises(FileNotFoundError) as context:
            self.hfe.remove_hosts_entry("1.1.1.1 example.com")
        self.assertIn(f"Error related to {self.mock_hosts_file_path}", str(context.exception))

    # --- Tests for update_hosts_file_content ---

    # NOTE: The original tests for `update_hosts_file_content` seem to be testing an older version
    # of the method or a different public interface. The `_update_hosts_file_content_direct` method
    # is internal and has a different signature. The following tests are for the internal method's
    # case-insensitive logic.
    # We will mock 'builtins.open' and 'HostsFileEdit.HOSTS_FILE' for these tests.
    # The logger_func can be None or a MagicMock.

    @patch('builtins.open', new_callable=mock_open)
    @patch.object(HostsFileEdit, 'HOSTS_FILE', '/mocked_hosts_file_for_test')
    def test_update_domain_is_case_insensitive_existing_same_ip(self, mock_open_file):
        hfe_instance = HostsFileEdit(logger_func=None)
        initial_content = ["1.1.1.1 WWW.EXAMPLE.COM\n"]
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = initial_content
        
        status, _ = hfe_instance._update_hosts_file_content_direct(
            staging_ip="1.1.1.1", sanitized_domain="www.example.com", delete=False
        )
        # If the only difference is case, and the file has "WWW.EXAMPLE.COM"
        # the current logic will normalize the case, resulting in a write and SUCCESS.
        self.assertEqual(status, Status.SUCCESS)
        
        handle = mock_open_file()
        written_content_lines = handle.writelines.call_args[0][0]
        self.assertEqual(written_content_lines, ["1.1.1.1 www.example.com\n"])

    @patch('builtins.open', new_callable=mock_open)
    @patch.object(HostsFileEdit, 'HOSTS_FILE', '/mocked_hosts_file_for_test')
    def test_update_domain_is_case_insensitive_existing_same_ip_already_lowercase(self, mock_open_file):
        hfe_instance = HostsFileEdit(logger_func=None)
        initial_content = ["1.1.1.1 www.example.com\n"] # Already lowercase, no comment
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = initial_content
        
        status, _ = hfe_instance._update_hosts_file_content_direct(
            staging_ip="1.1.1.1", sanitized_domain="www.example.com", delete=False
        )
        # Entry is exactly as it should be (lowercase, no comment), so ALREADY_EXISTS
        self.assertEqual(status, Status.ALREADY_EXISTS) 
        mock_open_file.return_value.__enter__.return_value.writelines.assert_not_called()


    @patch('builtins.open', new_callable=mock_open)
    @patch.object(HostsFileEdit, 'HOSTS_FILE', '/mocked_hosts_file_for_test')
    def test_update_domain_is_case_insensitive_existing_different_ip(self, mock_open_file):
        hfe_instance = HostsFileEdit(logger_func=None)
        initial_content = ["2.2.2.2 WWW.EXAMPLE.COM\n"]
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = initial_content
        
        status, _ = hfe_instance._update_hosts_file_content_direct(
            staging_ip="1.1.1.1", sanitized_domain="www.example.com", delete=False
        )
        self.assertEqual(status, Status.SUCCESS)
        
        handle = mock_open_file()
        written_content_lines = handle.writelines.call_args[0][0]
        # Ensure the new entry is present and the old one is gone
        self.assertIn("1.1.1.1 www.example.com\n", written_content_lines)
        self.assertNotIn("2.2.2.2 WWW.EXAMPLE.COM\n", written_content_lines) 
        self.assertEqual(len(written_content_lines), 1)


    @patch('builtins.open', new_callable=mock_open)
    @patch.object(HostsFileEdit, 'HOSTS_FILE', '/mocked_hosts_file_for_test')
    def test_add_new_domain_mixed_case_writes_lowercase(self, mock_open_file):
        hfe_instance = HostsFileEdit(logger_func=None)
        initial_content = ["1.2.3.4 other.com\n"]
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = initial_content
        
        status, _ = hfe_instance._update_hosts_file_content_direct(
            staging_ip="1.1.1.1", sanitized_domain="Mixed.Case.Com", delete=False
        )
        self.assertEqual(status, Status.SUCCESS)
        
        handle = mock_open_file()
        written_content_lines = handle.writelines.call_args[0][0]
        # Check that both original and new (lowercased) entries are present
        self.assertIn("1.2.3.4 other.com\n", written_content_lines)
        self.assertIn("1.1.1.1 mixed.case.com\n", written_content_lines)
        self.assertEqual(len(written_content_lines), 2)

    @patch('builtins.open', new_callable=mock_open)
    @patch.object(HostsFileEdit, 'HOSTS_FILE', '/mocked_hosts_file_for_test')
    def test_update_preserves_other_domains_casing_on_line(self, mock_open_file):
        hfe_instance = HostsFileEdit(logger_func=None)
        initial_content = ["1.1.1.1 WWW.EXAMPLE.COM OtherHost.com SOMEHOST.COM\n"]
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = initial_content
        
        status, _ = hfe_instance._update_hosts_file_content_direct(
            staging_ip="2.2.2.2", sanitized_domain="www.example.com", delete=False
        )
        self.assertEqual(status, Status.SUCCESS)
        
        handle = mock_open_file()
        written_content_lines = handle.writelines.call_args[0][0]
        
        # Check that other domains' casing is preserved and new entry is added
        self.assertIn("1.1.1.1 OtherHost.com SOMEHOST.COM\n", written_content_lines)
        self.assertIn("2.2.2.2 www.example.com\n", written_content_lines)
        self.assertEqual(len(written_content_lines), 2)


    @patch('builtins.open', new_callable=mock_open)
    @patch.object(HostsFileEdit, 'HOSTS_FILE', '/mocked_hosts_file_for_test')
    def test_add_same_domain_and_ip_twice_no_duplicates(self, mock_open_file):
        hfe_instance = HostsFileEdit(logger_func=None)
        
        # Call 1: Add for the first time
        initial_content1 = ["1.1.1.1 existing.com\n"]
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = initial_content1
        
        status1, _ = hfe_instance._update_hosts_file_content_direct(
            staging_ip="2.2.2.2", sanitized_domain="test.com", delete=False
        )
        self.assertEqual(status1, Status.SUCCESS)
        
        handle1 = mock_open_file()
        written_content_lines1 = handle1.writelines.call_args[0][0]
        
        # Call 2: Attempt to add the same entry again
        mock_open_file.return_value.__enter__.return_value.readlines.return_value = written_content_lines1
        handle1.writelines.reset_mock() 
        
        status2, _ = hfe_instance._update_hosts_file_content_direct(
            staging_ip="2.2.2.2", sanitized_domain="test.com", delete=False
        )
        self.assertEqual(status2, Status.ALREADY_EXISTS)

        handle1.writelines.assert_not_called()

        self.assertIn("1.1.1.1 existing.com\n", written_content_lines1)
        self.assertIn("2.2.2.2 test.com\n", written_content_lines1)
        count = sum(1 for line in written_content_lines1 if "2.2.2.2 test.com" in line.lower())
        self.assertEqual(count, 1, "The entry should only appear once.")


if __name__ == '__main__':
    unittest.main()

# Need to import Status for the tests to run
from akstaging.status_codes import Status

import unittest
from unittest.mock import patch, MagicMock, call
import tempfile
import os
import sys

# --- Start of Aggressive Mocking ---
mock_gi = MagicMock()
mock_gi.__path__ = ['dummy_path'] 
sys.modules['gi'] = mock_gi

mock_gi_repository = MagicMock()
sys.modules['gi.repository'] = mock_gi_repository
mock_gi.repository = mock_gi_repository

# Ensure Gio, GObject, Gtk, Adw are MagicMock modules initially
mock_gi_repository.Gio = MagicMock()
mock_gi_repository.GObject = MagicMock()
mock_gi_repository.Gtk = MagicMock()
mock_gi_repository.Adw = MagicMock()

# --- Define Mock Base Classes ---
class MockGObjectClass(object):
    def __init__(self, *args, **kwargs): super().__init__()
    __gsignals__ = {}
    _instance_init = MagicMock()
    @classmethod
    def bind_property(cls, *args, **kwargs): pass
    @classmethod
    def GObject(cls, *args, **kwargs): return cls(*args, **kwargs)
    @classmethod
    def new_template(cls, *args, **kwargs): pass
    @classmethod
    def set_template_from_resource(cls, *args, **kwargs): pass
    @classmethod
    def bind_template_child_full(cls, *args, **kwargs): pass
    @classmethod
    def get_template_child(cls, *args, **kwargs): return MagicMock()

mock_gi_repository.GObject.Object = MockGObjectClass
mock_gi_repository.GObject.TypeInstance = type 
mock_gi_repository.GObject.signal_lookup = MagicMock()
mock_gi_repository.GObject.add_interface = MagicMock()
mock_gi_repository.GObject.Property = MagicMock(return_value=property()) 
mock_gi_repository.GObject.param_spec_override = MagicMock()
mock_gi_repository.GObject.Binding = MagicMock()

class MockAdwApplicationWindow(MockGObjectClass): pass
mock_gi_repository.Adw.ApplicationWindow = MockAdwApplicationWindow
class MockGtkWidget(MockGObjectClass): pass
mock_gi_repository.Gtk.Widget = MockGtkWidget
class MockGtkWindow(MockGtkWidget): pass
mock_gi_repository.Gtk.Window = MockGtkWindow
class MockGtkApplicationWindow(MockGtkWindow): pass
mock_gi_repository.Gtk.ApplicationWindow = MockGtkApplicationWindow
mock_gi_repository.Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION = 1
mock_gi_repository.Gtk.CssProvider = MagicMock()
mock_gi_repository.Gtk.StyleContext = MagicMock()
mock_gi_repository.Adw.StyleManager = MagicMock()
mock_gi_repository.Gdk = MagicMock()
sys.modules['gi.repository.Gdk'] = mock_gi_repository.Gdk
mock_gi_repository.Gtk.Template = MagicMock(return_value=lambda cls: cls)
# --- End of Mock Base Classes ---

MockListStoreClass = MagicMock()
mock_list_store_instance = MagicMock()
mock_list_store_instance.append = MagicMock()
mock_list_store_instance.remove_all = MagicMock()
MockListStoreClass.new.return_value = mock_list_store_instance
mock_gi_repository.Gio.ListStore = MockListStoreClass 

sys.modules['gi.repository.Gio'] = mock_gi_repository.Gio
sys.modules['gi.repository.GObject'] = mock_gi_repository.GObject
sys.modules['gi.repository.Gtk'] = mock_gi_repository.Gtk
sys.modules['gi.repository.Adw'] = mock_gi_repository.Adw

# --- Other Application Mocks ---
mock_defs = MagicMock(); mock_defs.APP_NAME = "TestApp"; mock_defs.COPYRIGHT = "TestCopyright"
mock_defs.RESOURCE_PATH = "/test/resource/path"; mock_defs.VERSION = "0.0.test"
sys.modules['akstaging.defs'] = mock_defs

mock_dns_utils_module = MagicMock(); mock_DNSUtils_class = MagicMock() 
mock_dns_utils_module.DNSUtils = mock_DNSUtils_class
sys.modules['akstaging.dns_utils'] = mock_dns_utils_module

mock_dns_module = MagicMock(); sys.modules['dns'] = mock_dns_module
sys.modules['dns.exception'] = MagicMock()

mock_preferences_module = MagicMock(); mock_Preferences_class = MagicMock() 
mock_preferences_module.Preferences = mock_Preferences_class
sys.modules['akstaging.preferences'] = mock_preferences_module

mock_aklib_module = MagicMock(); mock_AkamaiLib_class = MagicMock()
mock_aklib_module.AkamaiLib = mock_AkamaiLib_class
mock_AkamaiLib_class.print_to_textview = MagicMock()
sys.modules['akstaging.aklib'] = mock_aklib_module


mock_HostsFileEdit_class_global = MagicMock() 
mock_hosts_module = MagicMock()
mock_hosts_module.HostsFileEdit = mock_HostsFileEdit_class_global
sys.modules['akstaging.hosts'] = mock_hosts_module
# --- End of Other Application Mocks ---

from akstaging.window import AkamaiStagingWindow, DataObject 
from akstaging.aklib import AkamaiLib

class TestDataObject: 
    def __init__(self, ip, hostname): self.ip = ip; self.hostname = hostname
    def __eq__(self, other):
        if not isinstance(other, TestDataObject): return NotImplemented
        return self.ip == other.ip and self.hostname == other.hostname
    def __repr__(self): return f"TestDataObject(ip='{self.ip}', hostname='{self.hostname}')"

class MockHFEInstanceForTest: 
    def __init__(self, hosts_file_path=None):
        self.HOSTS_FILE = hosts_file_path
    remove_hosts_entry = MagicMock()
    update_hosts_file_content = MagicMock()


class TestAkamaiStagingWindow(unittest.TestCase):
    
    def setUp(self):
        mock_list_store_instance.reset_mock()
        mock_list_store_instance.append.reset_mock()
        mock_list_store_instance.remove_all.reset_mock()
        mock_AkamaiLib_class.print_to_textview.reset_mock()
        
        mock_HostsFileEdit_class_global.reset_mock() 
        self.hfe_mock_instance = MockHFEInstanceForTest()
        mock_HostsFileEdit_class_global.return_value = self.hfe_mock_instance
        self.hfe_mock_instance.remove_hosts_entry.reset_mock()
        self.hfe_mock_instance.update_hosts_file_content.reset_mock()


    def test_populate_store(self):
        global mock_list_store_instance 
        mock_list_store_instance.append.reset_mock() 
        mock_list_store_instance.remove_all.reset_mock()

        self.assertFalse(isinstance(AkamaiStagingWindow, MagicMock), 
                         f"AkamaiStagingWindow is a {type(AkamaiStagingWindow)}, expected a class.")
        self.assertTrue(callable(AkamaiStagingWindow.populate_store), 
                        "AkamaiStagingWindow.populate_store should be a callable method.")

        hosts_content = [
            "1.2.3.4 example.com", "5.6.7.8", "# 9.10.11.12 commented.com", "",
            "127.0.0.1 localhost", "10.0.0.1 mydockercontainer", "4.3.2.1 another.example.com"
        ]
        
        with tempfile.NamedTemporaryFile(mode="w", delete=False, encoding="utf-8") as tmp_hosts:
            tmp_hosts.write("\n".join(hosts_content))
            tmp_hosts_path = tmp_hosts.name
        
        hfe_instance_for_populate_test = MockHFEInstanceForTest(hosts_file_path=tmp_hosts_path)

        with patch('akstaging.window.DataObject', new=TestDataObject), \
             patch('akstaging.window.logger', MagicMock()) as PatchedModuleLogger, \
             patch.object(AkamaiStagingWindow, '__init__', MagicMock(return_value=None)) as MockedClassInit:
            
            window_instance = AkamaiStagingWindow() 
            MockedClassInit.assert_called_once() 

            window_instance.hfe = hfe_instance_for_populate_test 
            window_instance.populate_store(mock_list_store_instance)

        mock_list_store_instance.remove_all.assert_called_once()
        expected_data_objects = [
            TestDataObject(ip="1.2.3.4", hostname="example.com"),
            TestDataObject(ip="4.3.2.1", hostname="another.example.com")
        ]
        self.assertEqual(mock_list_store_instance.append.call_count, len(expected_data_objects))
        actual_calls = mock_list_store_instance.append.call_args_list
        actual_data_objects = [c.args[0] for c in actual_calls]
        actual_data_objects.sort(key=lambda x: x.ip)
        expected_data_objects.sort(key=lambda x: x.ip)
        self.assertEqual(actual_data_objects, expected_data_objects)
        os.remove(tmp_hosts_path)

    def test_delete_entry_permission_error(self): 
        permission_msg = "Permission denied when trying to read or write to /etc/hosts. Root privileges may be required."
        self.hfe_mock_instance.remove_hosts_entry.side_effect = PermissionError(permission_msg)

        with patch.object(AkamaiStagingWindow, '__init__', MagicMock(return_value=None)) as MockedClassInit, \
             patch.object(AkamaiStagingWindow, 'populate_store', MagicMock()) as mock_populate_store_method:
            
            window_instance = AkamaiStagingWindow()
            MockedClassInit.assert_called_once()

            window_instance.selection_model = MagicMock()
            mock_selected_item = MagicMock()
            mock_selected_item.ip = "1.2.3.4"
            mock_selected_item.hostname = "baddomain.com"
            window_instance.selection_model.get_selected_item.return_value = mock_selected_item
            
            window_instance.hfe = self.hfe_mock_instance 
            window_instance.akl = mock_AkamaiLib_class.return_value 
            
            # Configure textview_status mock
            mock_text_buffer = MagicMock()
            mock_text_buffer.set_text = MagicMock()
            window_instance.textview_status = MagicMock()
            window_instance.textview_status.get_buffer = MagicMock(return_value=mock_text_buffer)
            window_instance.show_toast = MagicMock() # Mock show_toast
            window_instance.get_root = MagicMock() # Mock get_root for Adw.MessageDialog
            
            window_instance.on_delete_button_clicked(None, None) # This will internally call _on_delete_confirmation_response after dialog setup

            # Simulate clicking "delete" on the dialog.
            # The actual dialog is mocked, so we directly call the response handler.
            # We need to ensure _item_to_delete is set as it would be by on_delete_button_clicked
            window_instance._item_to_delete = mock_selected_item 
            window_instance._on_delete_confirmation_response(MagicMock(), "delete")


            self.hfe_mock_instance.remove_hosts_entry.assert_called_once_with("1.2.3.4 baddomain.com")
            
            # _handle_operation_error clears the buffer then prints.
            # So, the set_text("") from _on_delete_confirmation_response happens, 
            # then print_to_textview from _handle_operation_error happens.
            # We are asserting the call from _handle_operation_error.
            mock_AkamaiLib_class.print_to_textview.assert_called_once()
            args, _ = mock_AkamaiLib_class.print_to_textview.call_args
            self.assertEqual(args[0], window_instance.textview_status)
            self.assertIn("Failed to delete entry", args[1]) # Check prefix from _handle_operation_error
            self.assertIn(permission_msg, args[1])
            self.assertIn("Consider running with administrator privileges", args[1])
            
            window_instance.show_toast.assert_called_once()
            toast_args, _ = window_instance.show_toast.call_args
            self.assertIn("Failed to delete entry", toast_args[0]) # Check toast message
            self.assertIn("Permission denied", toast_args[0])

            mock_populate_store_method.assert_not_called()

    def test_get_ip_permission_error(self): 
        permission_msg = "Permission denied when trying to modify /etc/hosts. Root privileges may be required."
        self.hfe_mock_instance.update_hosts_file_content.side_effect = PermissionError(permission_msg)

        with patch.object(AkamaiStagingWindow, '__init__', MagicMock(return_value=None)) as MockedClassInit, \
             patch.object(AkamaiStagingWindow, 'populate_store', MagicMock()) as mock_populate_store_method:

            window_instance = AkamaiStagingWindow()
            MockedClassInit.assert_called_once()

            # Configure entry_domain mock
            window_instance.entry_domain = MagicMock()
            window_instance.entry_domain.get_text = MagicMock(return_value="example.com")
            
            mock_akl_instance = mock_AkamaiLib_class.return_value
            mock_akl_instance.sanitize_domain = MagicMock(return_value="example.com")
            window_instance.akl = mock_akl_instance
            
            window_instance.ns = mock_DNSUtils_class.return_value
            window_instance.ns.get_akamai_staging_ip = MagicMock(return_value="1.2.3.4")

            window_instance.hfe = self.hfe_mock_instance 

            # Configure textview_status mock
            mock_text_buffer = MagicMock()
            mock_text_buffer.set_text = MagicMock()
            window_instance.textview_status = MagicMock()
            window_instance.textview_status.get_buffer = MagicMock(return_value=mock_text_buffer)
            # window_instance.textview_status.set_margin_top = MagicMock() # This call was removed from window.py
            window_instance.show_toast = MagicMock() # Mock show_toast


            window_instance.on_get_ip_button_clicked(None, window_instance.entry_domain, window_instance.textview_status)

            mock_akl_instance.sanitize_domain.assert_called_once_with("example.com", window_instance.textview_status)
            window_instance.ns.get_akamai_staging_ip.assert_called_once_with("example.com", window_instance.textview_status)
            self.hfe_mock_instance.update_hosts_file_content.assert_called_once_with(
                "1.2.3.4", "example.com", False, window_instance.textview_status
            )
            
            # The initial text_buffer.set_text("") in on_get_ip_button_clicked is called.
            # Then _handle_operation_error calls print_to_textview.
            mock_text_buffer.set_text.assert_called_once_with("") # From on_get_ip_button_clicked
            mock_AkamaiLib_class.print_to_textview.assert_called_once()
            args, _ = mock_AkamaiLib_class.print_to_textview.call_args
            self.assertEqual(args[0], window_instance.textview_status)
            self.assertIn("Failed to get IP or update hosts file", args[1]) # Check prefix
            self.assertIn(permission_msg, args[1])
            self.assertIn("Consider running with administrator privileges", args[1])
            
            window_instance.show_toast.assert_called_once()
            toast_args, _ = window_instance.show_toast.call_args
            self.assertIn("Failed to get IP or update hosts file", toast_args[0]) # Check toast
            self.assertIn("Permission denied", toast_args[0])

            mock_populate_store_method.assert_not_called()

if __name__ == '__main__':
    unittest.main()

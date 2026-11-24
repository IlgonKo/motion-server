import tkinter as tk
import unittest
from unittest.mock import Mock
from control_panel.axis_control_panel.control_panel import AxisPanelBootstrap

class AxisBootstrapRecoveryTest(unittest.TestCase):
    def setUp(self):
        self.client = Mock(host='127.0.0.1', port=15000)
        self.client.owns_command_authority.return_value = False
        self.client.get_topology_snapshot.return_value = (0, '')
        self.client.get_snapshot.return_value = (True, '', {}, '', '')
        self.panel = AxisPanelBootstrap(self.client)
        self.panel.root.withdraw()

    def tearDown(self):
        try:
            for timer in self.panel.root.tk.call('after', 'info'):
                self.panel.root.after_cancel(timer)
            self.panel.root.destroy()
        except tk.TclError:
            pass

    def button(self, text):
        def walk(widget):
            for child in widget.winfo_children():
                if child.winfo_class() == 'TButton' and child.cget('text') == text:
                    return child
                found = walk(child)
                if found is not None:
                    return found
        button = walk(self.panel.root)
        self.assertIsNotNone(button, text)
        return button

    def test_zero_axes_has_working_reconnect_button(self):
        self.panel.update()
        self.assertIsNone(self.panel.result)
        self.button('Bus Reconnect').invoke()
        self.client.send_bus_reconnect.assert_called_once_with()
        self.client.request_command_authority.assert_not_called()

        def button_labels(widget):
            labels = []
            for child in widget.winfo_children():
                if child.winfo_class() == 'TButton':
                    labels.append(child.cget('text'))
                labels.extend(button_labels(child))
            return labels

        self.assertCountEqual(button_labels(self.panel.root),
                              ['Connect', 'Request Authority', 'Bus Reconnect'])

    def test_authority_is_explicit_and_fail_is_displayed(self):
        self.panel.root.update_idletasks()
        self.button('Request Authority').invoke()
        self.client.request_command_authority.assert_called_once_with()
        self.client.get_snapshot.return_value = (True, '', {}, 'Authority required', '')
        self.panel.update()
        self.assertEqual(self.panel.result_var.get(), 'Authority required')
        self.client.owns_command_authority.return_value = True
        self.panel.update()
        self.assertEqual(self.panel.authority_button_var.get(), 'Release Authority')
        self.panel.toggle_authority()
        self.client.release_command_authority.assert_called_once_with()

    def test_send_failure_and_disconnect_are_visible_without_resend(self):
        self.client.send_bus_reconnect.side_effect = ConnectionError('offline')
        self.button('Bus Reconnect').invoke()
        self.assertIn('offline', self.panel.result_var.get())
        self.client.get_snapshot.return_value = (False, 'Heartbeat timeout', {}, '', '')
        self.panel.update()
        self.assertIn('unconfirmed', self.panel.result_var.get())
        self.client.send_bus_reconnect.assert_called_once_with()

    def test_recovery_feedback_allows_normal_panel_handoff(self):
        self.client.get_topology_snapshot.return_value = (5, '')
        self.panel.update()
        self.assertEqual(self.panel.result, 5)

if __name__ == '__main__':
    unittest.main()

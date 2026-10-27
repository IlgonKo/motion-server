"""Headless GUI failure/cleanup tests; no real Tk or server needed."""
import time
import unittest
from pathlib import Path
from .headless_widgets import install, Root
from .gui import Panel
from .sequence import Feedback
from .test_sequence import FakeClient

class GuiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): install()

    def exercise(self,mode):
        root=Root(); panel=Panel(root)
        panel.config.update(request_timeout=.2,feedback_timeout=.12,stage_timeout=.24,input_timeout=.15)
        c=FakeClient(mode); f=Feedback(c); f.start()
        def stop():
            c.is_connected=False
            c.close()
        c.stop=stop
        panel.client=c; panel.feedback=f; panel.metadata_ok=True
        stage='start'; deadline=time.monotonic()+4; outcome={}
        def drive():
            nonlocal stage
            self.assertLess(time.monotonic(),deadline)
            if stage=='start' and f.snapshot()[2]:
                panel.run(); stage='run'
            elif stage=='run' and not panel.busy:
                outcome['state']=panel.sequence.state
                outcome['confirmed']=panel.sequence.cleanup_confirmed
                outcome['logs']=list(panel.history)
                panel.close(); stage='close'
            if not panel.closed: root.after(10,drive)
        root.after(10,drive)
        try: root.mainloop()
        finally: c.close(); f.close()
        self.assertTrue(panel.closed)
        return outcome

    def test_failure_is_not_hidden_when_closing(self):
        for mode in ('stop_fail','disconnect','authority','request_timeout'):
            with self.subTest(mode=mode):
                out=self.exercise(mode)
                self.assertEqual(out['state'],'failed')
                if mode!='request_timeout':
                    self.assertFalse(out['confirmed'])
                    self.assertTrue(any('NOT confirmed' in line for line in out['logs']))

    def test_missing_config_blocks_run_and_can_close(self):
        root=Root(); panel=Panel(root,Path(__file__).with_name('missing-config.json'))
        self.assertTrue(panel.config_error)
        panel.run()
        self.assertIsNone(panel.sequence)
        panel.close(); root.mainloop()
        self.assertTrue(panel.closed)

if __name__=='__main__': unittest.main(verbosity=2)

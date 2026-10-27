from pathlib import Path
p=Path('generated/test_gui_mock.py')
s=p.read_text(encoding='utf-8').replace('import json','import json\nimport sys',1)
s=s.replace("    config=load_config()", "    headless='--headless' in sys.argv\n    if headless:\n        from .headless_widgets import install\n        install()\n        print('HEADLESS callback/worker test; real Tk/OS interaction NOT tested.',flush=True)\n    config=load_config()")
s=s.replace("Path('generated/gui_result.json')", "Path('generated/gui_headless_result.json' if headless else 'generated/gui_result.json')")
s=s.replace("    print('All GUI Mock tests passed; no test window remains.',flush=True)","    print('All '+('headless GUI callback' if headless else 'real Tk GUI')+' Mock tests passed; no test window remains.',flush=True)")
p.write_text(s,encoding='utf-8')

import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from scripts.windows import service_package


ROOT = Path(__file__).resolve().parents[1]


class WindowsServicePackageTests(unittest.TestCase):
    def test_template_matches_agreed_scm_defaults_without_server_log_capture(self):
        root = ET.parse(ROOT / "packaging/windows_service/MotionServerService.default.xml").getroot()
        self.assertEqual(root.findtext("id"), "MotionServer")
        self.assertEqual(root.findtext("name"), "Motion Server")
        self.assertEqual(root.findtext("startmode"), "Automatic")
        self.assertEqual(root.findtext("stoptimeout"), "30 sec")
        self.assertEqual(root.findtext("resetfailure"), "1 day")
        self.assertEqual([e.attrib for e in root.findall("onfailure")], [
            {"action": "restart", "delay": "5 sec"},
            {"action": "restart", "delay": "5 sec"}, {"action": "none"}])
        self.assertIsNone(root.find("serviceaccount"))  # WinSW default LocalSystem
        self.assertEqual(root.find("log").get("mode"), "none")

    def test_package_rejects_corrupt_download_before_writing_executable(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "SHA-256 mismatch"):
                service_package.build(directory, download=lambda *a, **k: io.BytesIO(b"corrupt"))
            self.assertFalse((Path(directory) / "Tools/service/MotionServerService.exe").exists())

    def test_package_includes_license_script_and_pinned_binary(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory) / "source"
            target = Path(directory) / "package"
            source = fixture / "packaging/windows_service"
            source.mkdir(parents=True)
            scripts = fixture / "scripts/windows"
            scripts.mkdir(parents=True)
            (scripts / "register_service.ps1").write_text("fixture", encoding="utf-8")
            (source / "MotionServerService.default.xml").write_text("<service/>", encoding="utf-8")
            (source / "dependency.json").write_text(json.dumps({
                "url": "binary", "sha256": hashlib.sha256(b"binary").hexdigest(),
                "license_url": "license"}), encoding="utf-8")
            with patch.object(service_package, "ROOT", fixture):
                service_package.build(target, download=lambda url, **k: io.BytesIO(url.encode()))
            self.assertEqual((target / "Tools/service/MotionServerService.exe").read_bytes(), b"binary")
            self.assertTrue((target / "Tools/service/WinSW-LICENSE.txt").exists())
            self.assertTrue((target / "register_service.ps1").exists())

    @unittest.skipUnless(os.name == "nt", "PowerShell registration contract")
    def test_registration_paths_with_mocked_scm_never_start_or_stop_services(self):
        # No administrator privileges or actual Windows service calls are used.
        shell = shutil.which("pwsh") or shutil.which("powershell")
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            service = base / "Tools/service"
            service.mkdir(parents=True)
            for name in ("motion_server.exe", "config.txt"):
                (base / name).write_text("fixture", encoding="utf-8")
            (service / "MotionServerService.exe").write_bytes(b"fixture")
            (service / "dependency.json").write_text(json.dumps({
                "sha256": hashlib.sha256(b"fixture").hexdigest()}), encoding="utf-8")
            shutil.copy2(ROOT / "packaging/windows_service/MotionServerService.default.xml", service)
            script_path = str(ROOT / "scripts/windows/register_service.ps1").replace("'", "''")
            package_path = str(base).replace("'", "''")
            script = f". '{script_path}'\n$root = '{package_path}'\n" + r'''
function Test-ServiceRegistrationAdministrator { return $script:isAdmin }
function Get-MotionServerService {
    if ($script:statuses.Count -eq 0) { return $null }
    $status = $script:statuses.Dequeue()
    if ($status -eq 'Absent') { return $null }
    $result = [pscustomobject]@{Status=$status}
    $result | Add-Member -MemberType ScriptMethod -Name Dispose -Value {}
    return $result
}
function Invoke-ServiceRegistrationCommand {
    param($Executable, $Arguments)
    $script:commands.Add(($Arguments -join ' '))
    if ($script:failCommand -eq $Arguments[0]) { throw 'injected command failure' }
}
function Start-Service { throw 'Start-Service must never be called' }
function Stop-Service { throw 'Stop-Service must never be called' }
$results = @()
foreach ($case in @('new','replace','running','pending','noadmin','deletefail','installfail')) {
    $script:isAdmin = $case -ne 'noadmin'
    $script:commands = [System.Collections.Generic.List[string]]::new()
    $script:statuses = [System.Collections.Generic.Queue[string]]::new()
    $script:failCommand = ''
    if ($case -in @('replace','deletefail')) { $script:statuses.Enqueue('Stopped') }
    if ($case -eq 'running') { $script:statuses.Enqueue('Running') }
    if ($case -eq 'pending') { $script:statuses.Enqueue('StopPending') }
    if ($case -eq 'deletefail') { $script:failCommand = 'delete' }
    if ($case -eq 'installfail') { $script:failCommand = 'install' }
    $errorText = ''
    try { Register-MotionServerService -Root $root *> $null }
    catch { $errorText = $_.Exception.Message }
    $results += [pscustomobject]@{case=$case; commands=@($script:commands.ToArray()); error=$errorText}
}
$results | ConvertTo-Json -Depth 5 -Compress
'''
            harness = base / "contract.ps1"
            harness.write_text(script, encoding="utf-8-sig")
            run = subprocess.run([shell, "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(harness)],
                                 capture_output=True, text=True, timeout=20)
            self.assertEqual(run.returncode, 0, run.stderr)
            cases = {item["case"]: item for item in json.loads(run.stdout)}
            self.assertEqual(cases["new"]["commands"], ["install"])
            self.assertEqual(cases["replace"]["commands"], ["delete MotionServer", "install"])
            self.assertEqual(cases["new"]["error"], "")
            self.assertEqual(cases["replace"]["error"], "")
            for name in ("running", "pending", "noadmin"):
                self.assertEqual(cases[name]["commands"], [])
                self.assertTrue(cases[name]["error"])
            self.assertEqual(cases["deletefail"]["commands"], ["delete MotionServer"])
            self.assertTrue(cases["deletefail"]["error"])
            self.assertTrue(cases["installfail"]["error"])


if __name__ == "__main__":
    unittest.main()

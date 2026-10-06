using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.Text;

namespace CodexTokenHud
{
    internal sealed class RuntimeConfiguration
    {
        internal string Folder, DataDirectory, CodexHome, Pythonw;
        internal string Runtime { get { return Path.Combine(DataDirectory, "runtime"); } }
        internal string Layout { get { return Path.Combine(DataDirectory, "user-layout.json"); } }

        internal static RuntimeConfiguration Load(string folder)
        {
            folder = Path.GetFullPath(folder);
            string customData = Environment.GetEnvironmentVariable("CODEX_TOKEN_HUD_HOME");
            var result = new RuntimeConfiguration { Folder = folder,
                DataDirectory = Path.GetFullPath(string.IsNullOrWhiteSpace(customData) ?
                    Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData), "CodexTokenHud") : customData) };
            var settings = Json.Read(Path.Combine(folder, "settings.json"));
            var userSettings = Json.Read(Path.Combine(result.DataDirectory, "settings.json"));
            foreach (var item in userSettings) settings[item.Key] = item.Value;
            string home = Json.Text(settings, "codex_home");
            if (string.IsNullOrWhiteSpace(home)) home = Environment.GetEnvironmentVariable("CODEX_HOME");
            if (string.IsNullOrWhiteSpace(home)) home = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.UserProfile), ".codex");
            result.CodexHome = Path.GetFullPath(Environment.ExpandEnvironmentVariables(home));
            string python = Json.Text(settings, "pythonw");
            if (!string.IsNullOrWhiteSpace(python))
            {
                python = Environment.ExpandEnvironmentVariables(python);
                result.Pythonw = Path.GetFullPath(Path.IsPathRooted(python) ? python : Path.Combine(folder, python));
            }
            else
            {
                var candidates = new List<string> { Path.Combine(folder, "python", "pythonw.exe") };
                foreach (string path in (Environment.GetEnvironmentVariable("PATH") ?? "").Split(Path.PathSeparator))
                    if (!string.IsNullOrWhiteSpace(path))
                        try { candidates.Add(Path.Combine(path.Trim('"'), "pythonw.exe")); } catch (ArgumentException) { }
                result.Pythonw = candidates.Find(File.Exists);
            }
            return result;
        }

        internal void PrepareData()
        {
            Directory.CreateDirectory(DataDirectory);
            Directory.CreateDirectory(Runtime);
            // Preserve existing installations' layout once, without publishing or moving their files.
            string oldLayout = Path.Combine(Folder, "user-layout.json");
            if (string.IsNullOrEmpty(Environment.GetEnvironmentVariable("CODEX_TOKEN_HUD_HOME")) &&
                !File.Exists(Layout) && File.Exists(oldLayout)) File.Copy(oldLayout, Layout);
        }

        internal string CheckPython()
        {
            if (string.IsNullOrEmpty(Pythonw) || !File.Exists(Pythonw))
                throw new InvalidOperationException("Python runtime not found. Extract the full portable ZIP, or set pythonw in settings.json. / 请解压完整便携包，或配置 Python 3.10+。");
            string consolePython = Path.Combine(Path.GetDirectoryName(Pythonw), "python.exe");
            if (!File.Exists(consolePython)) throw new InvalidOperationException("python.exe is missing next to pythonw.exe.");
            using (var process = Process.Start(new ProcessStartInfo(consolePython,
                "-I -X utf8 -c \"import sqlite3, ctypes, json, sys; print('.'.join(map(str, sys.version_info[:3])))\"") {
                UseShellExecute = false, CreateNoWindow = true, RedirectStandardOutput = true,
                RedirectStandardError = true, WindowStyle = ProcessWindowStyle.Hidden }))
            {
                if (!process.WaitForExit(5000)) { process.Kill(); throw new InvalidOperationException("Python runtime check timed out."); }
                string version = process.StandardOutput.ReadToEnd().Trim();
                Version parsed;
                if (process.ExitCode != 0 || !Version.TryParse(version, out parsed) || parsed.Major != 3 || parsed.Minor < 10)
                    throw new InvalidOperationException("Python 3.10+ with sqlite3 is required.");
                return version;
            }
        }

        internal static string Quote(string argument)
        {
            // Escape for Windows CommandLineToArgvW / C runtime; no shell is involved.
            var result = new StringBuilder("\"");
            int slashes = 0;
            foreach (char c in argument)
            {
                if (c == '\\') { slashes++; continue; }
                result.Append('\\', c == '"' ? slashes * 2 + 1 : slashes);
                result.Append(c); slashes = 0;
            }
            result.Append('\\', slashes * 2).Append('"');
            return result.ToString();
        }
    }
}

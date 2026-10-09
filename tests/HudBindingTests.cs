using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Windows.Forms;
using CodexTokenHud;

// Exercise our own forms and temporary binding/layout data; never inspect or control Codex.
class HudBindingTests
{
    const BindingFlags Private = BindingFlags.Instance | BindingFlags.NonPublic;
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr window, int command);
    static int checks;
    static object Call(Hud hud, string name, params object[] args)
    { return typeof(Hud).GetMethod(name, Private).Invoke(hud, args); }
    static object Field(Hud hud, string name)
    { return typeof(Hud).GetField(name, Private).GetValue(hud); }
    static void Check(bool condition, string name)
    { if (!condition) throw new Exception(name); checks++; Console.WriteLine("PASS " + name); }
    static ToolStripItem Item(Hud hud, string text)
    {
        Call(hud, "BuildMenu");
        return ((ContextMenuStrip)Field(hud, "menu")).Items.Cast<ToolStripItem>().SingleOrDefault(i => i.Text == text);
    }
    class FixtureWindow : Form
    { protected override bool ShowWithoutActivation { get { return true; } } }

    [STAThread] static int Main(string[] args)
    {
        var root = Path.GetFullPath(args[0]);
        var temporary = Path.Combine(root, "build", "tests", "binding-" + Guid.NewGuid().ToString("N"));
        var config = new RuntimeConfiguration { Folder = root, DataDirectory = temporary,
            CodexHome = Path.Combine(temporary, "empty-codex"), Pythonw = args[1] };
        Hud hud = null;
        try
        {
            config.PrepareData();
            Json.Write(config.Layout, new Dictionary<string, object> {
                {"mode", "manual"}, {"x", 12}, {"y", 23}, {"width", 800}, {"height", 38} });
            string savedLayout = File.ReadAllText(config.Layout);
            Json.Write(Path.Combine(config.Runtime, "manual-binding.json"), new Dictionary<string, object> {
                {"thread_id", "fixture-id"}, {"title", "Pinned fixture"} });
            hud = new Hud(config);
            ((System.Windows.Forms.Timer)Field(hud, "ticker")).Stop();
            double now = (DateTime.UtcNow - new DateTime(1970, 1, 1)).TotalMilliseconds;
            typeof(Hud).GetField("data", Private).SetValue(hud, new Dictionary<string, object> {
                {"title", "Pinned fixture"}, {"thread_id", "fixture-id"}, {"binding", "ok"}, {"updated_at_ms", now},
                {"source", new Dictionary<string, object> {{"state", "ok"}}},
                {"metrics", new Dictionary<string, object> {
                    {"model", "fixture-model"}, {"stage", "idle"},
                    {"last", new Dictionary<string, object> {
                        {"model", "fixture-model"}, {"measured_at_ms", now - 1000}, {"rate", 22.0}, {"cache_percent", 75.0} }} }} });
            hud.StartMonitoring();
            Check(Native.IsWindowVisible(hud.Handle) && Native.IsTopmost(hud.Handle) &&
                (string)Field(hud, "rateText") == "22.0", "startup shows the fixed conversation as a native topmost window");
            var foreground = Native.GetForegroundWindow();
            Native.SetWindowPos(hud.Handle, new IntPtr(-2), 0, 0, 0, 0, 0x13);
            Check(hud.TopMost && !Native.IsTopmost(hud.Handle), "fixture reproduces cached TopMost differing from Windows");
            Call(hud, "PositionHud");
            Check(Native.IsTopmost(hud.Handle) && Native.GetForegroundWindow() == foreground,
                "positioning repairs native topmost without taking focus");
            Native.SetWindowLongPtr(hud.Handle, -20, new IntPtr(Native.GetWindowLongPtr(hud.Handle, -20).ToInt64() & ~8L));
            Call(hud, "PositionHud");
            Check(Native.IsTopmost(hud.Handle) && Native.GetForegroundWindow() == foreground,
                "positioning repairs a topmost style inconsistent with the native z-order band");
            Native.SetWindowPos(hud.Handle, IntPtr.Zero, 0, 0, 0, 0, 0x97);
            Check(hud.Visible && !Native.IsWindowVisible(hud.Handle), "fixture reproduces a natively hidden managed-visible strip");
            Call(hud, "PositionHud");
            Check(Native.IsWindowVisible(hud.Handle) && Native.IsTopmost(hud.Handle) && Native.GetForegroundWindow() == foreground,
                "positioning repairs native visibility without taking focus");
            ShowWindow(hud.Handle, 7);
            Check(Native.IsIconic(hud.Handle), "fixture reproduces a minimized legacy shortcut launch");
            foreground = Native.GetForegroundWindow();
            Call(hud, "PositionHud");
            Check(!Native.IsIconic(hud.Handle) && Native.IsWindowVisible(hud.Handle) && Native.IsTopmost(hud.Handle) &&
                Native.GetForegroundWindow() == foreground, "positioning restores a minimized strip without taking focus");
            Check(Item(hud, "按对话 ID 固定状态栏…") != null, "fixed mode has ID picker entry");
            var pinnedBounds = hud.Bounds;
            Item(hud, "解除固定，自动跟随桌面对话").PerformClick();
            Check(!hud.IsDisposed && Native.IsWindowVisible(hud.Handle) && Native.IsTopmost(hud.Handle) &&
                hud.Bounds == pinnedBounds, "unpin retains a native visible topmost live form and position");
            var selection = Json.Read(Path.Combine(config.Runtime, "selection.json"));
            Check(Json.Text(selection, "binding_mode") == "auto" && string.IsNullOrEmpty(Json.Text(selection, "thread_id")),
                "unpin clears the previous fixed selection immediately");
            Check((string)Field(hud, "rateText") == "--" && (string)Field(hud, "modelText") == "正在识别当前对话",
                "waiting state does not show previous conversation measurements");
            Check(Item(hud, "按对话 ID 固定状态栏…") != null, "auto waiting mode retains ID picker entry");
            hud.Bounds = new Rectangle(pinnedBounds.X + 10, pinnedBounds.Y, pinnedBounds.Width + 20, pinnedBounds.Height);
            var moved = hud.Bounds;
            Call(hud, "SaveLayout");
            Call(hud, "PositionHud");
            Check(hud.Bounds == moved && File.ReadAllText(config.Layout) == savedLayout,
                "moving the waiting strip preserves the saved automatic layout");
            using (var owner = new FixtureWindow { ShowInTaskbar = false, Size = new Size(900, 300) })
            {
                owner.Show();
                Call(hud, "UpdateView", new ViewSnapshot { Handle = owner.Handle,
                    ProcessId = (uint)Process.GetCurrentProcess().Id, Title = "Next fixture", Primary = true });
                Call(hud, "UpdateMetrics");
                Call(hud, "PositionHud");
                Check(Json.Text(Json.Read(Path.Combine(config.Runtime, "selection.json")), "title") == "Next fixture",
                    "automatic discovery can bind the next conversation");
                Check(Native.IsWindowVisible(hud.Handle) && (bool)Field(hud, "waitingForAutoFocus"),
                    "unpin keeps the strip accessible while the discovered window is in the background");
                Call(hud, "UpdateView", new ViewSnapshot { Handle = owner.Handle,
                    ProcessId = Native.ProcessId(Native.GetForegroundWindow()), Title = "Next fixture", Primary = true });
                Call(hud, "PositionHud");
                Check(!(bool)Field(hud, "waitingForAutoFocus") && Native.IsTopmost(hud.Handle),
                    "automatic tracking resumes above the matching foreground process");
                Check(Native.GetWindow(hud.Handle, 4) == IntPtr.Zero, "HUD has no foreign window owner");
                hud.Hide();
                string showRequest = Path.Combine(config.Runtime, "show.request.json");
                Json.Write(showRequest, new Dictionary<string, object> {{"requested_at", DateTime.UtcNow.ToString("o")}});
                Call(hud, "ConsumeShowRequest");
                Check(!File.Exists(showRequest) && Native.IsWindowVisible(hud.Handle) && Native.IsTopmost(hud.Handle),
                    "repeat-launch request is consumed and restores the native window");
                Check(Item(hud, "显示状态栏") != null, "tray menu retains a show-strip recovery entry");
                owner.Close();
                Call(hud, "UpdateView", new object[] { null });
                Call(hud, "UpdateMetrics");
                Call(hud, "PositionHud");
                Check(!hud.IsDisposed && Native.IsWindowVisible(hud.Handle) && Native.IsTopmost(hud.Handle),
                    "loss of the followed window returns to native visible waiting instead of exiting");
            }
            Console.WriteLine("Binding checks passed: " + checks);
            return 0;
        }
        catch (Exception error) { Console.Error.WriteLine(error); return 1; }
        finally
        {
            if (hud != null) { hud.Close(); hud.Dispose(); }
            // Only this test's validated temporary child is removed.
            if (Path.GetFullPath(temporary).StartsWith(Path.Combine(root, "build", "tests") + Path.DirectorySeparatorChar,
                StringComparison.OrdinalIgnoreCase)) Directory.Delete(temporary, true);
        }
    }
}

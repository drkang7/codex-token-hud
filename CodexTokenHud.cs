using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics;
using System.Drawing;
using System.Drawing.Drawing2D;
using System.Globalization;
using System.IO;
using System.Linq;
using System.Runtime.InteropServices;
using System.Text;
using System.Threading;
using System.Threading.Tasks;
using System.Web.Script.Serialization;
using System.Windows.Automation;
using System.Windows.Forms;

namespace CodexTokenHud
{
    internal static class Native
    {
        internal delegate bool EnumProc(IntPtr h, IntPtr state);
        [StructLayout(LayoutKind.Sequential)] internal struct Rect { public int Left, Top, Right, Bottom; }
        [StructLayout(LayoutKind.Sequential)] internal struct Point { public int X, Y; }
        [DllImport("user32.dll")] internal static extern bool EnumWindows(EnumProc callback, IntPtr state);
        [DllImport("user32.dll")] internal static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
        [DllImport("user32.dll")] internal static extern bool GetClientRect(IntPtr h, out Rect rect);
        [DllImport("user32.dll")] internal static extern bool ClientToScreen(IntPtr h, ref Point point);
        [DllImport("user32.dll")] internal static extern bool IsWindow(IntPtr h);
        [DllImport("user32.dll")] internal static extern bool IsWindowVisible(IntPtr h);
        [DllImport("user32.dll")] internal static extern bool IsIconic(IntPtr h);
        [DllImport("user32.dll")] internal static extern IntPtr GetForegroundWindow();
        [DllImport("user32.dll")] internal static extern IntPtr GetAncestor(IntPtr h, uint flags);
        [DllImport("user32.dll")] internal static extern uint GetDpiForWindow(IntPtr h);
        [DllImport("user32.dll")] internal static extern bool SetProcessDpiAwarenessContext(IntPtr context);
        [DllImport("user32.dll", EntryPoint="SetWindowLongPtrW")] internal static extern IntPtr SetWindowLongPtr(IntPtr h, int index, IntPtr value);

        internal static double Scale(IntPtr h)
        {
            try { uint dpi = GetDpiForWindow(h); return dpi > 0 ? dpi / 96.0 : 1.0; }
            catch (EntryPointNotFoundException) { return 1.0; }
        }
        internal static uint ProcessId(IntPtr h) { uint id; GetWindowThreadProcessId(h, out id); return id; }
        internal static List<IntPtr> Windows()
        {
            var pids = new HashSet<uint>(Process.GetProcessesByName("ChatGPT").Select(p => (uint)p.Id));
            var result = new List<IntPtr>();
            EnumWindows(delegate(IntPtr h, IntPtr state) {
                if (pids.Contains(ProcessId(h)) && IsWindowVisible(h) && !IsIconic(h)) result.Add(h);
                return true;
            }, IntPtr.Zero);
            return result;
        }
    }

    internal sealed class ViewSnapshot
    {
        internal IntPtr Handle;
        internal uint ProcessId;
        internal string Title;
        internal int PaneLeft;
        internal bool Primary;
        internal AutomationElement RootElement;
        internal AutomationElement TitleElement;
    }

    internal static class Inspector
    {
        internal static ViewSnapshot Read(IntPtr handle, HashSet<string> titles)
        {
            var result = new ViewSnapshot { Handle = handle, ProcessId = Native.ProcessId(handle) };
            try
            {
                var root = AutomationElement.FromHandle(handle);
                if (root == null) return result;
                var bounds = root.Current.BoundingRectangle;
                double scale = Native.Scale(handle);
                var request = new CacheRequest();
                request.Add(AutomationElement.NameProperty);
                request.Add(AutomationElement.ControlTypeProperty);
                request.Add(AutomationElement.BoundingRectangleProperty);
                request.Add(AutomationElement.IsOffscreenProperty);
                request.AutomationElementMode = AutomationElementMode.Full;
                var condition = new OrCondition(
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Text),
                    new PropertyCondition(AutomationElement.ControlTypeProperty, ControlType.Button));
                var header = new List<AutomationElement>();
                using (request.Activate())
                {
                    var elements = root.FindAll(TreeScope.Descendants, condition);
                    foreach (AutomationElement element in elements)
                    {
                        var c = element.Cached;
                        var box = c.BoundingRectangle;
                        if (c.IsOffscreen || box.IsEmpty || double.IsInfinity(box.Left) ||
                            box.Top < bounds.Top || box.Top > bounds.Top + 160 * scale) continue;
                        string name = c.Name;
                        if (string.IsNullOrEmpty(name) || name.Length > 160) continue;
                        if (c.ControlType == ControlType.Button &&
                            (name == "聊天操作" || name == "Chat actions" || name == "Thread actions" ||
                             name.StartsWith("切换模式，当前模式") || name.StartsWith("Switch mode"))) result.Primary = true;
                        if (c.ControlType == ControlType.Text && box.Top > bounds.Top + 42 * scale &&
                            box.Top < bounds.Top + 108 * scale && box.Left > bounds.Left + 100 * scale)
                            header.Add(element);
                    }
                }
                if (!result.Primary) return result;
                var title = header.FirstOrDefault(e => titles.Contains(e.Cached.Name));
                if (title == null) title = header.OrderBy(e => e.Cached.BoundingRectangle.Top).FirstOrDefault();
                if (title != null)
                {
                    result.Title = title.Cached.Name;
                    result.PaneLeft = Math.Max(0, (int)(title.Cached.BoundingRectangle.Left - bounds.Left - 40 * scale));
                    result.RootElement = root;
                    result.TitleElement = title;
                }
                else result.PaneLeft = (int)(72 * scale);
            }
            catch (ElementNotAvailableException) { }
            catch (Exception) { }
            return result;
        }

        private static ViewSnapshot ReadCached(ViewSnapshot previous, HashSet<string> titles)
        {
            try
            {
                if (previous.TitleElement != null && previous.RootElement != null)
                {
                    var current = previous.TitleElement.Current;
                    var bounds = previous.RootElement.Current.BoundingRectangle;
                    var box = current.BoundingRectangle;
                    double scale = Native.Scale(previous.Handle);
                    if (!current.IsOffscreen && !box.IsEmpty && !string.IsNullOrEmpty(current.Name) &&
                        box.Top > bounds.Top + 42 * scale && box.Top < bounds.Top + 108 * scale &&
                        box.Left > bounds.Left + 100 * scale)
                        return new ViewSnapshot { Handle = previous.Handle, ProcessId = previous.ProcessId,
                            Primary = true, Title = current.Name, RootElement = previous.RootElement,
                            TitleElement = previous.TitleElement,
                            PaneLeft = Math.Max(0, (int)(box.Left - bounds.Left - 40 * scale)) };
                }
            }
            catch (Exception) { }
            return Read(previous.Handle, titles);
        }

        internal static ViewSnapshot Find(ViewSnapshot previous, HashSet<string> titles)
        {
            IntPtr preferred = previous == null ? IntPtr.Zero : previous.Handle;
            // A second Codex window can be foreground while the previous window stays open.
            IntPtr foreground = Native.GetForegroundWindow();
            if (foreground != IntPtr.Zero && foreground != preferred && Native.IsWindowVisible(foreground))
            {
                uint foregroundPid = Native.ProcessId(foreground);
                if (Process.GetProcessesByName("ChatGPT").Any(p => p.Id == foregroundPid))
                {
                    var active = Read(foreground, titles);
                    if (active.Primary) return active;
                }
            }
            if (preferred != IntPtr.Zero && Native.IsWindow(preferred) && !Native.IsIconic(preferred))
            {
                var snapshot = ReadCached(previous, titles);
                if (snapshot.Primary) return snapshot;
            }
            foreach (var h in Native.Windows().OrderByDescending(h => h == Native.GetForegroundWindow()))
            {
                var snapshot = Read(h, titles);
                if (snapshot.Primary) return snapshot;
            }
            return null;
        }
    }

    internal sealed class MetricDisplay
    {
        internal string Model = "等待统计", Rate = "--", Cache = "缓存 待统计", Stage = "等待绑定", Freshness = "等待数据";
        internal double? SampleAgeMs, CollectorAgeMs;
        internal bool Fresh;
        internal static string Number(double? value) { return value.HasValue ? value.Value.ToString("0.0", CultureInfo.InvariantCulture) : "--"; }
        internal static string Age(double milliseconds)
        {
            double seconds = Math.Max(0, milliseconds / 1000);
            if (seconds < 1) return "刚刚";
            if (seconds < 60) return ((int)seconds).ToString() + "秒前";
            if (seconds < 3600) return ((int)(seconds / 60)).ToString() + "分钟前";
            if (seconds < 86400) return ((int)(seconds / 3600)).ToString() + "小时前";
            return ((int)(seconds / 86400)).ToString() + "天前";
        }

        internal static MetricDisplay Read(Dictionary<string, object> data, string title, double nowMs)
        {
            var result = new MetricDisplay();
            bool bound = Json.Text(data, "title") == title && Json.Text(data, "binding") == "ok";
            var metrics = bound ? Json.Object(data, "metrics") : null;
            result.Model = Json.Text(metrics, "model");
            if (string.IsNullOrEmpty(result.Model)) result.Model = string.IsNullOrEmpty(title) ? "打开本地对话" : "等待统计";
            if (!bound) {
                string repository = Json.Text(data, "repository_state");
                result.Stage = repository == "missing" ? "未找到本地对话" : repository == "unsupported" ? "数据库版本待适配" :
                    repository == "unavailable" ? "数据库暂不可读" : Json.Text(data, "binding") == "ambiguous" ? "同名对话 · 右键选择" : "等待绑定";
                return result;
            }
            double? heartbeat = Json.Number(data, "updated_at_ms");
            result.CollectorAgeMs = heartbeat.HasValue ? Math.Max(0, nowMs - heartbeat.Value) : (double?)null;
            if (!heartbeat.HasValue || result.CollectorAgeMs > 6000)
            { result.Stage = "采集器重连中"; result.Freshness = "数据未更新"; return result; }
            string source = Json.Text(Json.Object(data, "source"), "state");
            if (source == "unavailable" || source == "catching_up")
            { result.Stage = source == "unavailable" ? "日志不可读" : "同步最新日志"; return result; }
            string stage = Json.Text(metrics, "stage");
            result.Stage = stage == "tools" ? "工具运行中" : stage == "generating" ? "生成中" : "最近响应";
            var last = Json.Object(metrics, "last");
            if (last != null && !string.IsNullOrEmpty(Json.Text(last, "model")) && Json.Text(last, "model") != result.Model) last = null;
            double? measured = Json.Number(last, "measured_at_ms");
            if (!measured.HasValue) { result.Freshness = "等待新统计"; return result; }
            result.SampleAgeMs = Math.Max(0, nowMs - measured.Value);
            double? turnStart = Json.Number(metrics, "turn_started_at_ms");
            if (turnStart.HasValue && turnStart.Value > measured.Value && stage != "idle")
            { result.Freshness = "本轮待统计"; return result; }
            if (result.SampleAgeMs >= 15 * 60 * 1000)
            { result.Cache = "缓存 历史"; result.Freshness = "历史 " + Age(result.SampleAgeMs.Value); return result; }
            result.Rate = Number(Json.Number(last, "rate"));
            result.Cache = "缓存 " + (Json.Number(last, "cache_percent").HasValue ? Number(Json.Number(last, "cache_percent")) + "%" : "暂无数据");
            result.Freshness = "更新 " + Age(result.SampleAgeMs.Value);
            result.Fresh = true;
            return result;
        }
    }

    internal static class Json
    {
        internal static Dictionary<string, object> Read(string file)
        {
            try
            {
                using (var stream = new FileStream(file, FileMode.Open, FileAccess.Read, FileShare.ReadWrite | FileShare.Delete))
                using (var reader = new StreamReader(stream, Encoding.UTF8, true))
                    return new JavaScriptSerializer().Deserialize<Dictionary<string, object>>(reader.ReadToEnd());
            }
            catch { return new Dictionary<string, object>(); }
        }
        internal static object Get(Dictionary<string, object> value, string key)
        { object result; return value != null && value.TryGetValue(key, out result) ? result : null; }
        internal static string Text(Dictionary<string, object> value, string key)
        { return Convert.ToString(Get(value, key), CultureInfo.InvariantCulture); }
        internal static double? Number(Dictionary<string, object> value, string key)
        {
            var o = Get(value, key); if (o == null) return null;
            try { return Convert.ToDouble(o, CultureInfo.InvariantCulture); } catch { return null; }
        }
        internal static Dictionary<string, object> Object(Dictionary<string, object> value, string key)
        { return Get(value, key) as Dictionary<string, object>; }
        internal static IEnumerable<Dictionary<string, object>> List(Dictionary<string, object> value, string key)
        {
            var array = Get(value, key) as IEnumerable;
            if (array == null) yield break;
            foreach (var o in array) { var d = o as Dictionary<string, object>; if (d != null) yield return d; }
        }
        internal static void Write(string file, Dictionary<string, object> value)
        {
            try
            {
                Directory.CreateDirectory(Path.GetDirectoryName(file));
                var temporary = file + ".new";
                File.WriteAllText(temporary, new JavaScriptSerializer().Serialize(value), new UTF8Encoding(false));
                if (File.Exists(file)) File.Replace(temporary, file, null); else File.Move(temporary, file);
            }
            catch { }
        }
    }

    internal sealed class Hud : Form
    {
        private readonly RuntimeConfiguration configuration;
        private readonly string folder;
        private readonly string runtime;
        private readonly System.Windows.Forms.Timer ticker = new System.Windows.Forms.Timer();
        private readonly ToolTip tooltip = new ToolTip { InitialDelay = 250, AutoPopDelay = 25000, ReshowDelay = 100 };
        private readonly ContextMenuStrip menu = new ContextMenuStrip();
        private readonly NotifyIcon tray = new NotifyIcon();
        private Process backend;
        private ViewSnapshot view;
        private Dictionary<string, object> data = new Dictionary<string, object>();
        private DateTime nextInspection = DateTime.MinValue;
        private DateTime lastStatus = DateTime.MinValue;
        private DateTime nextBackendCheck = DateTime.MinValue;
        private bool inspecting;
        private bool stopping;
        private bool manualLayout;
        private bool sizingOrMoving;
        private double relativeX;
        private double relativeY;
        private double layoutWidth = 900;
        private double layoutHeight = 38;
        private string selectedTitle = "";
        private string pinnedId;
        private string previousSelection = "";
        private string rateText = "--";
        private string modelText = "等待对话";
        private string cacheText = "缓存 --";
        private string weeklyText = "本对话周额度 暂无数据";
        private string stageText = "";
        private string freshnessText = "等待数据";
        private bool fresh;
        private double? sampleAgeMs;
        private double? collectorAgeMs;
        private long refreshId;
        private string helpText = "打开本地对话后自动显示。右键可以选择同名对话或退出。";
        private double scale = 1;
        private Rectangle closeRect { get { return new Rectangle(Width - (int)(26 * scale) - 4, 3, (int)(26 * scale), Height - 6); } }
        private Rectangle infoRect { get { var close = closeRect; return new Rectangle(close.Left - close.Width, 3, close.Width, Height - 6); } }
        private readonly Font smallFont = new Font("Microsoft YaHei UI", 9.0f, FontStyle.Regular);
        private readonly Font labelFont = new Font("Microsoft YaHei UI", 9.5f, FontStyle.Regular);
        private readonly Font speedFont = new Font("Segoe UI", 13.0f, FontStyle.Bold);

        internal Hud(RuntimeConfiguration configuration)
        {
            this.configuration = configuration;
            folder = configuration.Folder;
            configuration.PrepareData();
            runtime = configuration.Runtime;
            Text = "Codex Token 状态条";
            FormBorderStyle = FormBorderStyle.None;
            ShowInTaskbar = false;
            StartPosition = FormStartPosition.Manual;
            AutoScaleMode = AutoScaleMode.None;
            DoubleBuffered = true;
            BackColor = Color.FromArgb(18, 31, 43);
            Size = new Size(1040, 40);
            ContextMenuStrip = menu;
            var layout = Json.Read(configuration.Layout);
            manualLayout = Json.Text(layout, "mode") == "manual";
            relativeX = Json.Number(layout, "x") ?? 0;
            relativeY = Json.Number(layout, "y") ?? 0;
            layoutWidth = Json.Number(layout, "width") ?? 900;
            layoutHeight = Json.Number(layout, "height") ?? 38;
            menu.Opening += delegate { BuildMenu(); };
            tray.Icon = SystemIcons.Information;
            tray.Text = "Codex Token 状态条";
            tray.ContextMenuStrip = menu;
            tray.Visible = true;
            tray.DoubleClick += delegate { RequestRefresh(); };
            ticker.Interval = 150;
            ticker.Tick += Tick;
            StartBackend();
            ticker.Start();
        }
        protected override bool ShowWithoutActivation { get { return true; } }
        protected override CreateParams CreateParams
        {
            get {
                var cp = base.CreateParams;
                cp.ExStyle |= 0x08000000 | 0x00000080;
                cp.Style |= 0x00040000; // Native sizing support; custom client area keeps the strip frameless.
                return cp;
            }
        }
        internal void StartMonitoring() { var unused = Handle; Hide(); }

        private void StartBackend()
        {
            try
            {
                var args = "-I -X utf8 " + RuntimeConfiguration.Quote(Path.Combine(folder, "metrics.py")) +
                    " --runtime " + RuntimeConfiguration.Quote(runtime) + " --codex-home " + RuntimeConfiguration.Quote(configuration.CodexHome) +
                    " --parent-pid " + Process.GetCurrentProcess().Id;
                backend = Process.Start(new ProcessStartInfo(configuration.Pythonw, args) {
                    UseShellExecute = false, CreateNoWindow = true, WorkingDirectory = folder, WindowStyle = ProcessWindowStyle.Hidden });
            }
            catch (Exception) { modelText = "采集器未启动"; }
        }

        private void Tick(object sender, EventArgs e)
        {
            if (stopping) return;
            data = Json.Read(Path.Combine(runtime, "metrics.json"));
            if (DateTime.UtcNow >= nextBackendCheck)
            {
                nextBackendCheck = DateTime.UtcNow.AddSeconds(1);
                try
                {
                    double? heartbeat = Json.Number(data, "updated_at_ms");
                    if (backend != null && !backend.HasExited &&
                        DateTime.UtcNow - backend.StartTime.ToUniversalTime() > TimeSpan.FromSeconds(10) &&
                        (!heartbeat.HasValue || EpochMs() - heartbeat.Value > 10000)) backend.Kill();
                    if (backend == null || backend.HasExited) StartBackend();
                }
                catch { StartBackend(); }
            }
            if (!inspecting && DateTime.UtcNow >= nextInspection)
            {
                inspecting = true;
                nextInspection = DateTime.UtcNow.AddMilliseconds(350);
                var known = new HashSet<string>(Json.List(data, "threads").Select(t => Json.Text(t, "title")));
                var preferred = view;
                Task.Run(delegate { return Inspector.Find(preferred, known); }).ContinueWith(task => {
                    if (stopping || IsDisposed) return;
                    try { BeginInvoke(new Action(delegate {
                        inspecting = false;
                        if (task.Status == TaskStatus.RanToCompletion) UpdateView(task.Result);
                    })); } catch { }
                });
            }
            UpdateMetrics();
            PositionHud();
            string previewRequest = Path.Combine(runtime, "preview.request");
            if (File.Exists(previewRequest))
            {
                File.Delete(previewRequest);
                using (var bitmap = new Bitmap(Width, Height))
                {
                    using (var graphics = Graphics.FromImage(bitmap))
                    {
                        graphics.Clear(BackColor);
                        OnPaint(new PaintEventArgs(graphics, new Rectangle(Point.Empty, Size)));
                    }
                    bitmap.Save(Path.Combine(runtime, "hud-preview.png"), System.Drawing.Imaging.ImageFormat.Png);
                }
            }
            if (DateTime.UtcNow >= lastStatus)
            {
                lastStatus = DateTime.UtcNow.AddSeconds(1);
                Json.Write(Path.Combine(runtime, "status.json"), new Dictionary<string, object> {
                    {"pid", Process.GetCurrentProcess().Id}, {"visible", Visible},
                    {"window", view == null ? 0L : view.Handle.ToInt64()}, {"title", selectedTitle},
                    {"thread_id", Json.Text(data, "thread_id")}, {"rate_text", rateText},
                    {"model_text", modelText}, {"cache_text", cacheText}, {"weekly_text", weeklyText},
                    {"layout_mode", manualLayout ? "manual" : "auto"},
                    {"freshness", freshnessText}, {"sample_age_ms", sampleAgeMs}, {"collector_age_ms", collectorAgeMs},
                    {"source", Json.Object(data, "source")},
                    {"stage", stageText}, {"left", Left}, {"top", Top}, {"width", Width}, {"height", Height},
                    {"updated_at", DateTime.UtcNow.ToString("o")} });
            }
        }

        private void UpdateView(ViewSnapshot snapshot)
        {
            view = snapshot;
            string title = snapshot == null ? "" : snapshot.Title ?? "";
            if (title != selectedTitle) pinnedId = null;
            selectedTitle = title;
            string key = title + "\n" + pinnedId;
            if (key == previousSelection) return;
            previousSelection = key;
            Json.Write(Path.Combine(runtime, "selection.json"), new Dictionary<string, object> {
                {"title", title}, {"thread_id", pinnedId}, {"refresh_id", refreshId},
                {"window", snapshot == null ? 0L : snapshot.Handle.ToInt64()}});
        }

        private void RequestRefresh()
        {
            refreshId = DateTime.UtcNow.Ticks;
            previousSelection = "";
            nextInspection = DateTime.MinValue;
            UpdateView(view);
        }

        private void PositionHud()
        {
            if (view == null || !Native.IsWindow(view.Handle) || Native.IsIconic(view.Handle) || !Native.IsWindowVisible(view.Handle))
            { if (Visible) Hide(); return; }
            IntPtr foreground = Native.GetForegroundWindow();
            bool codexFocused = Native.ProcessId(foreground) == view.ProcessId || foreground == Handle || menu.Visible;
            Native.Rect client;
            Native.Point origin = new Native.Point();
            if (!Native.GetClientRect(view.Handle, out client) || !Native.ClientToScreen(view.Handle, ref origin)) return;
            scale = Native.Scale(view.Handle);
            MinimumSize = new Size((int)(420 * scale), (int)(32 * scale));
            int h = (int)Math.Round(38 * scale);
            int margin = (int)Math.Round(7 * scale);
            int pane = Math.Min(view.PaneLeft, Math.Max(0, client.Right - (int)(420 * scale)));
            int w = client.Right - pane - margin * 2;
            if (w < (int)(360 * scale)) { if (Visible) Hide(); return; }
            var wanted = new Rectangle(origin.X + pane + margin, origin.Y + client.Bottom - h - margin, w, h);
            if (manualLayout)
            {
                wanted = new Rectangle(origin.X + (int)Math.Round(relativeX * scale), origin.Y + (int)Math.Round(relativeY * scale),
                    Math.Max(MinimumSize.Width, (int)Math.Round(layoutWidth * scale)),
                    Math.Max(MinimumSize.Height, (int)Math.Round(layoutHeight * scale)));
                // Preserve a grab area if a display has been disconnected since the last run.
                var area = Screen.FromHandle(view.Handle).WorkingArea;
                wanted.X = Math.Max(area.Left - wanted.Width + (int)(120 * scale), Math.Min(wanted.X, area.Right - (int)(120 * scale)));
                wanted.Y = Math.Max(area.Top, Math.Min(wanted.Y, area.Bottom - (int)(32 * scale)));
            }
            if (!sizingOrMoving && Bounds != wanted) Bounds = wanted;
            Native.SetWindowLongPtr(Handle, -8, view.Handle); // Owned by Codex, follows its z-order without stealing focus.
            if (!codexFocused) { if (Visible) Hide(); return; }
            if (!Visible) Show();
            Invalidate();
        }

        private static string Format(double? n) { return n.HasValue ? n.Value.ToString("0.0", CultureInfo.InvariantCulture) : "--"; }
        private static double EpochMs() { return (DateTime.UtcNow - new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc)).TotalMilliseconds; }
        private static string TimeLabel(double? milliseconds)
        {
            if (!milliseconds.HasValue || milliseconds.Value <= 0) return "未知";
            try { return new DateTime(1970, 1, 1, 0, 0, 0, DateTimeKind.Utc).AddMilliseconds(milliseconds.Value).ToLocalTime().ToString("MM-dd HH:mm:ss"); }
            catch { return "未知"; }
        }

        private void UpdateMetrics()
        {
            bool bound = Json.Text(data, "title") == selectedTitle && Json.Text(data, "binding") == "ok";
            var metrics = bound ? Json.Object(data, "metrics") : null;
            var last = Json.Object(metrics, "last");
            var display = MetricDisplay.Read(data, selectedTitle, EpochMs());
            modelText = display.Model;
            if (last != null && !string.IsNullOrEmpty(Json.Text(last, "model")) && Json.Text(last, "model") != modelText) last = null;
            rateText = display.Rate;
            cacheText = display.Cache;
            stageText = display.Stage;
            freshnessText = display.Freshness;
            sampleAgeMs = display.SampleAgeMs;
            collectorAgeMs = display.CollectorAgeMs;
            fresh = display.Fresh;
            weeklyText = "本对话周额度 暂无数据";
            var help = new StringBuilder();
            help.AppendLine("当前对话：" + (string.IsNullOrEmpty(selectedTitle) ? "未识别" : selectedTitle));
            help.AppendLine("模型：" + modelText);
            help.AppendLine("速率：最近一次模型响应的真实输出 token / 生成秒数。");
            help.AppendLine("每 0.1 秒检查新统计，界面每 0.15 秒刷新；实际计数在模型响应完成后到达。");
            help.AppendLine("当前状态：" + stageText + " · " + freshnessText);
            help.AppendLine("新一轮尚无计数、统计超过 15 分钟或采集器失联时显示 --，旧响应详情仍可在下方查看。");
            help.AppendLine("包含推理 token；不重复相加。隐藏的逐 token 流没有公开实时计数。");
            if (last != null)
            {
                help.AppendLine("输出 " + Format(Json.Number(last, "output_tokens")) + " token，计时 " +
                    Format(Json.Number(last, "duration_ms") / 1000) + " 秒（" +
                    (Json.Text(last, "basis") == "stream" ? "首个模型流式条目至响应结束" : "请求耗时，含首 token 等待") + "）。");
                help.AppendLine("缓存命中率：" + Format(Json.Number(last, "cached_input_tokens")) + " / " +
                    Format(Json.Number(last, "input_tokens")) + " 输入 token = " + Format(Json.Number(last, "cache_percent")) + "%");
                help.AppendLine("最近已完成响应的统计时间：" + TimeLabel(Json.Number(last, "measured_at_ms")));
            }
            help.AppendLine("采集心跳：" + TimeLabel(Json.Number(data, "updated_at_ms")));
            help.AppendLine("本对话周额度：当前服务未提供按对话归属的周额度扣减值，无法精确统计。");
            help.AppendLine("按住条内区域拖动；拖动边缘或右下角调整大小。位置和尺寸自动保存。");
            help.AppendLine("右键可立即刷新数据、恢复底部默认位置、选择同名对话、设置开机启动或退出。");
            helpText = help.ToString();
            if (tooltip.GetToolTip(this) != helpText) tooltip.SetToolTip(this, helpText);
        }

        protected override void OnPaint(PaintEventArgs e)
        {
            base.OnPaint(e);
            e.Graphics.SmoothingMode = SmoothingMode.AntiAlias;
            using (var pen = new Pen(Color.FromArgb(68, 91, 109))) e.Graphics.DrawRectangle(pen, 0, 0, Width - 1, Height - 1);
            int x = (int)(13 * scale);
            int dot = (int)(7 * scale);
            using (var brush = new SolidBrush(fresh ? Color.FromArgb(87, 225, 196) : Color.FromArgb(148, 172, 191))) e.Graphics.FillEllipse(brush, x, (Height - dot) / 2, dot, dot);
            x += (int)(15 * scale);
            DrawPart(e.Graphics, modelText, smallFont, Color.FromArgb(194, 207, 221), ref x, Math.Min((int)(190 * scale), Width / 5));
            Divider(e.Graphics, ref x);
            DrawPart(e.Graphics, "速率", labelFont, Color.FromArgb(220, 228, 236), ref x, 0);
            DrawPart(e.Graphics, rateText, speedFont, Color.FromArgb(87, 225, 196), ref x, 0);
            DrawPart(e.Graphics, "tok/s", smallFont, Color.FromArgb(187, 205, 219), ref x, 0);
            int cacheRoom = TextRenderer.MeasureText(e.Graphics, cacheText, labelFont).Width + (int)(22 * scale);
            int ageRoom = TextRenderer.MeasureText(e.Graphics, freshnessText, smallFont).Width + (int)(20 * scale);
            int reserved = cacheRoom + ageRoom + (int)(105 * scale);
            if (Width - x > reserved + (int)(410 * scale)) DrawPart(e.Graphics, stageText, smallFont, Color.FromArgb(148, 172, 191), ref x, (int)(105 * scale));
            if (Width - x > reserved + (int)(265 * scale))
            {
                Divider(e.Graphics, ref x);
                DrawPart(e.Graphics, weeklyText, smallFont, Color.FromArgb(146, 165, 180), ref x, (int)(215 * scale));
            }
            Divider(e.Graphics, ref x);
            int cacheWidth = Math.Max(0, Width - x - ageRoom - (int)(80 * scale));
            if (cacheWidth > 0) DrawPart(e.Graphics, cacheText, labelFont, Color.FromArgb(169, 204, 255), ref x, cacheWidth);
            Divider(e.Graphics, ref x);
            DrawPart(e.Graphics, freshnessText, smallFont, fresh ? Color.FromArgb(148, 172, 191) : Color.FromArgb(240, 195, 125), ref x, Math.Max(1, Width - x - (int)(60 * scale)));
            TextRenderer.DrawText(e.Graphics, "×", labelFont, closeRect, Color.FromArgb(168, 187, 201), TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
            TextRenderer.DrawText(e.Graphics, "?", labelFont, infoRect, Color.FromArgb(168, 187, 201), TextFormatFlags.HorizontalCenter | TextFormatFlags.VerticalCenter);
            using (var grip = new Pen(Color.FromArgb(117, 143, 163)))
                for (int n = 1; n <= 3; n++) e.Graphics.DrawLine(grip, Width - (int)((3 + n * 3) * scale), Height - (int)(3 * scale),
                    Width - (int)(3 * scale), Height - (int)((3 + n * 3) * scale));
        }

        private void DrawPart(Graphics graphics, string text, Font font, Color color, ref int x, int maximum)
        {
            int wanted = TextRenderer.MeasureText(graphics, text, font, new Size(int.MaxValue, Height), TextFormatFlags.NoPadding | TextFormatFlags.SingleLine).Width + (int)(7 * scale);
            int width = maximum > 0 ? Math.Min(wanted, maximum) : wanted;
            width = Math.Min(width, Math.Max(0, Width - x - (int)(60 * scale)));
            if (width > 0) TextRenderer.DrawText(graphics, text, font, new Rectangle(x, 0, width, Height), color,
                TextFormatFlags.VerticalCenter | TextFormatFlags.SingleLine | TextFormatFlags.EndEllipsis | TextFormatFlags.NoPadding);
            x += width;
        }
        private void Divider(Graphics graphics, ref int x)
        {
            x += (int)(9 * scale);
            using (var pen = new Pen(Color.FromArgb(66, 84, 99))) graphics.DrawLine(pen, x, (int)(11 * scale), x, Height - (int)(11 * scale));
            x += (int)(12 * scale);
        }
        protected override void OnMouseClick(MouseEventArgs e)
        {
            base.OnMouseClick(e);
            if (e.Button != MouseButtons.Left) return;
            if (closeRect.Contains(e.Location)) Close();
            else if (infoRect.Contains(e.Location)) tooltip.Show(helpText, this, Math.Max(0, Width - (int)(520 * scale)), -(int)(180 * scale), 20000);
        }
        protected override void WndProc(ref Message m)
        {
            const int hitTest = 0x0084, calcSize = 0x0083, enterSizeMove = 0x0231, exitSizeMove = 0x0232;
            if (m.Msg == calcSize && m.WParam != IntPtr.Zero) { m.Result = IntPtr.Zero; return; }
            if (m.Msg == hitTest)
            {
                long coordinates = m.LParam.ToInt64();
                var point = PointToClient(new Point((short)(coordinates & 0xffff), (short)((coordinates >> 16) & 0xffff)));
                int edge = Math.Max(5, (int)(6 * scale));
                bool left = point.X < edge, right = point.X >= Width - edge;
                bool top = point.Y < edge, bottom = point.Y >= Height - edge;
                int hit = top && left ? 13 : top && right ? 14 : bottom && left ? 16 : bottom && right ? 17 :
                    left ? 10 : right ? 11 : top ? 12 : bottom ? 15 :
                    closeRect.Contains(point) || infoRect.Contains(point) ? 1 : 2;
                m.Result = new IntPtr(hit);
                return;
            }
            if (m.Msg == enterSizeMove) { manualLayout = true; sizingOrMoving = true; }
            if (m.Msg == 0x00a5) { BuildMenu(); menu.Show(Cursor.Position); m.Result = IntPtr.Zero; return; }
            if (m.Msg == 0x00a3) { m.Result = IntPtr.Zero; return; } // Double-clicking does not maximize a status strip.
            base.WndProc(ref m);
            if (m.Msg == exitSizeMove) { sizingOrMoving = false; SaveLayout(); }
        }

        private void SaveLayout()
        {
            if (!manualLayout || view == null || !Native.IsWindow(view.Handle)) return;
            Native.Point origin = new Native.Point();
            if (!Native.ClientToScreen(view.Handle, ref origin)) return;
            double dpiScale = Native.Scale(view.Handle);
            relativeX = (Left - origin.X) / dpiScale;
            relativeY = (Top - origin.Y) / dpiScale;
            layoutWidth = Width / dpiScale;
            layoutHeight = Height / dpiScale;
            Json.Write(configuration.Layout, new Dictionary<string, object> {
                {"mode", "manual"}, {"x", relativeX}, {"y", relativeY}, {"width", layoutWidth}, {"height", layoutHeight} });
        }

        private void ResetLayout()
        {
            manualLayout = false;
            Json.Write(configuration.Layout, new Dictionary<string, object> {{"mode", "auto"}});
            PositionHud();
        }
        private string StartupTaskName { get { return "CodexTokenHud-" + Environment.UserName; } }

        private bool IsStartupEnabled()
        {
            try
            {
                dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
                service.Connect();
                dynamic root = service.GetFolder("\\");
                dynamic task = root.GetTask(StartupTaskName);
                bool enabled = task.Enabled && string.Equals((string)task.Definition.Actions[1].Path,
                    Application.ExecutablePath, StringComparison.OrdinalIgnoreCase);
                Marshal.FinalReleaseComObject(task); Marshal.FinalReleaseComObject(root); Marshal.FinalReleaseComObject(service);
                return enabled;
            }
            catch { return false; }
        }

        private void SetStartup(bool enabled)
        {
            dynamic service = Activator.CreateInstance(Type.GetTypeFromProgID("Schedule.Service"));
            service.Connect();
            dynamic root = service.GetFolder("\\");
            dynamic existing = null;
            try { existing = root.GetTask(StartupTaskName); }
            catch (COMException error) { if (error.ErrorCode != unchecked((int)0x80070002)) throw; }
            if (existing != null)
            {
                string path = (string)existing.Definition.Actions[1].Path;
                Marshal.FinalReleaseComObject(existing);
                if (!string.Equals(path, Application.ExecutablePath, StringComparison.OrdinalIgnoreCase))
                    throw new InvalidOperationException("同名启动任务指向另一个副本；请先在原副本中关闭自动启动。");
            }
            if (!enabled) root.DeleteTask(StartupTaskName, 0);
            else
            {
                string user = System.Security.Principal.WindowsIdentity.GetCurrent().Name;
                dynamic definition = service.NewTask(0);
                definition.RegistrationInfo.Description = "Codex 当前对话 token 速率和缓存命中率状态条";
                definition.Principal.UserId = user;
                definition.Principal.LogonType = 3; // Only run in this user's interactive session.
                definition.Principal.RunLevel = 1; // Match an elevated Codex window's UI Automation access.
                definition.Settings.ExecutionTimeLimit = "PT0S";
                definition.Settings.MultipleInstances = 2;
                definition.Settings.DisallowStartIfOnBatteries = false;
                definition.Settings.StopIfGoingOnBatteries = false;
                definition.Settings.StartWhenAvailable = true;
                dynamic trigger = definition.Triggers.Create(9);
                trigger.UserId = user;
                trigger.Delay = "PT10S";
                dynamic action = definition.Actions.Create(0);
                action.Path = Application.ExecutablePath;
                action.WorkingDirectory = folder;
                dynamic task = root.RegisterTaskDefinition(StartupTaskName, definition, 6, user, null, 3, null);
                Marshal.FinalReleaseComObject(task); Marshal.FinalReleaseComObject(action);
                Marshal.FinalReleaseComObject(trigger); Marshal.FinalReleaseComObject(definition);
            }
            Marshal.FinalReleaseComObject(root); Marshal.FinalReleaseComObject(service);
        }
        private void BuildMenu()
        {
            menu.Items.Clear();
            var heading = menu.Items.Add("当前：" + (string.IsNullOrEmpty(selectedTitle) ? "未识别对话" : selectedTitle));
            heading.Enabled = false;
            var candidates = Json.List(data, "matches").ToList();
            if (candidates.Count > 1)
            {
                foreach (var row in candidates)
                {
                    string id = Json.Text(row, "id");
                    string label = Json.Text(row, "model") + " · " + id.Substring(Math.Max(0, id.Length - 8));
                    var item = menu.Items.Add("绑定 " + label) as ToolStripMenuItem;
                    item.Checked = pinnedId == id;
                    item.Click += delegate { pinnedId = id; previousSelection = ""; UpdateView(view); };
                }
            }
            var refresh = menu.Items.Add("立即刷新数据");
            refresh.Click += delegate { RequestRefresh(); };
            menu.Items.Add("恢复底部默认位置和大小").Click += delegate { ResetLayout(); };
            var startup = menu.Items.Add("开机自动启动") as ToolStripMenuItem;
            startup.Checked = IsStartupEnabled();
            startup.Click += delegate {
                try { SetStartup(!IsStartupEnabled()); }
                catch (Exception error) { MessageBox.Show("无法修改开机启动：" + error.Message, Text, MessageBoxButtons.OK, MessageBoxIcon.Information); }
            };
            var readme = menu.Items.Add("打开使用说明");
            readme.Click += delegate { Process.Start(Path.Combine(folder, "README.zh-CN.md")); };
            menu.Items.Add(new ToolStripSeparator());
            menu.Items.Add("退出状态条").Click += delegate { Close(); };
        }

        internal void CreateShortcut(string path)
        {
            Type type = Type.GetTypeFromProgID("WScript.Shell");
            dynamic shell = Activator.CreateInstance(type);
            dynamic link = shell.CreateShortcut(path);
            link.TargetPath = Application.ExecutablePath;
            link.WorkingDirectory = folder;
            link.Description = "在 Codex 窗口底部显示当前对话的 token 速率和缓存命中率，支持拖动和缩放";
            link.WindowStyle = 7;
            link.Save();
            Marshal.FinalReleaseComObject(link);
            Marshal.FinalReleaseComObject(shell);
        }

        protected override void OnFormClosing(FormClosingEventArgs e)
        {
            stopping = true;
            SaveLayout();
            ticker.Stop();
            tray.Visible = false;
            try { if (backend != null && !backend.HasExited) backend.Kill(); } catch { }
            smallFont.Dispose(); labelFont.Dispose(); speedFont.Dispose(); tooltip.Dispose(); tray.Dispose();
            base.OnFormClosing(e);
        }
        protected override void OnFormClosed(FormClosedEventArgs e)
        {
            base.OnFormClosed(e);
            Application.ExitThread();
        }
    }

    internal static class Program
    {
        [STAThread] private static int Main(string[] args)
        {
            RuntimeConfiguration configuration;
            try
            {
                configuration = RuntimeConfiguration.Load(AppDomain.CurrentDomain.BaseDirectory);
                string pythonVersion = configuration.CheckPython();
                if (args.Length == 2 && args[0] == "--check")
                {
                    Json.Write(Path.GetFullPath(args[1]), new Dictionary<string, object> {
                        {"ok", true}, {"python_version", pythonVersion},
                        {"bundled_python", configuration.Pythonw.StartsWith(Path.Combine(configuration.Folder, "python"), StringComparison.OrdinalIgnoreCase)},
                        {"app_version", Application.ProductVersion} });
                    return 0;
                }
                configuration.PrepareData();
            }
            catch (Exception error)
            {
                if (args.Length == 2 && args[0] == "--check")
                    Json.Write(Path.GetFullPath(args[1]), new Dictionary<string, object> {{"ok", false}, {"error", error.Message}});
                else MessageBox.Show(error.Message, "Codex Token HUD", MessageBoxButtons.OK, MessageBoxIcon.Information);
                return 1;
            }
            bool owner;
            using (var singleton = new Mutex(true, "Local\\CodexTokenHud-v1-" + Environment.UserName, out owner))
            {
                if (!owner) return 0;
                try { Native.SetProcessDpiAwarenessContext(new IntPtr(-4)); } catch { }
                Application.EnableVisualStyles();
                Application.SetCompatibleTextRenderingDefault(false);
                var hud = new Hud(configuration);
                hud.StartMonitoring();
                Application.Run();
                singleton.ReleaseMutex();
            }
            return 0;
        }
    }
}

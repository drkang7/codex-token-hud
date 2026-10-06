using System;
using System.Collections.Generic;
using System.IO;
using CodexTokenHud;

class PresentationTests
{
    static int checks;
    static Dictionary<string, object> Fixture(double now)
    {
        return new Dictionary<string, object> {
            {"title", "current"}, {"binding", "ok"}, {"updated_at_ms", now},
            {"source", new Dictionary<string, object> {{"state", "ok"}}},
            {"metrics", new Dictionary<string, object> {
                {"model", "model-a"}, {"stage", "idle"}, {"turn_started_at_ms", now - 5000},
                {"last", new Dictionary<string, object> {
                    {"model", "model-a"}, {"measured_at_ms", now - 1000}, {"rate", 22.0}, {"cache_percent", 75.0} }} }} };
    }
    static void Check(bool condition, string name)
    { if (!condition) throw new Exception(name); checks++; Console.WriteLine("PASS " + name); }
    static void Main()
    {
        double now = 1800000000000;
        var data = Fixture(now);
        var display = MetricDisplay.Read(data, "current", now);
        Check(display.Rate == "22.0" && display.Cache == "缓存 75.0%" && display.Freshness == "更新 1秒前", "recent sample");

        data = Fixture(now);
        Json.Object(Json.Object(data, "metrics"), "last")["measured_at_ms"] = now - 2 * 86400000.0;
        display = MetricDisplay.Read(data, "current", now);
        Check(display.Rate == "--" && !display.Fresh && display.Freshness == "历史 2天前", "old sample is not current speed");

        data = Fixture(now);
        Json.Object(data, "metrics")["stage"] = "generating";
        Json.Object(data, "metrics")["turn_started_at_ms"] = now - 500;
        display = MetricDisplay.Read(data, "current", now);
        Check(display.Rate == "--" && display.Cache == "缓存 待统计" && display.Freshness == "本轮待统计", "new turn hides previous counts");

        data = Fixture(now); data["updated_at_ms"] = now - 10000;
        display = MetricDisplay.Read(data, "current", now);
        Check(display.Rate == "--" && display.Stage == "采集器重连中", "collector heartbeat expired");

        data = Fixture(now); Json.Object(data, "source")["state"] = "unavailable";
        display = MetricDisplay.Read(data, "current", now);
        Check(display.Rate == "--" && display.Stage == "日志不可读", "unreadable log hides cached result");

        data = Fixture(now); Json.Object(data, "metrics")["model"] = "model-b";
        display = MetricDisplay.Read(data, "current", now);
        Check(display.Rate == "--" && display.Freshness == "等待新统计", "model switch hides previous model sample");

        data = Fixture(now);
        display = MetricDisplay.Read(data, "another chat", now);
        Check(display.Rate == "--" && display.Stage == "等待绑定", "chat switch hides previous chat sample");

        data = Fixture(now); Json.Object(data, "metrics")["last"] = null;
        display = MetricDisplay.Read(data, "current", now);
        Check(display.Rate == "--" && display.Freshness == "等待新统计", "no measurements");

        foreach (string state in new [] { "missing", "unsupported", "unavailable" })
        {
            data = Fixture(now); data["binding"] = "unbound"; data["repository_state"] = state;
            display = MetricDisplay.Read(data, "current", now);
            Check(display.Rate == "--" && display.Stage != "等待绑定", "database status " + state);
        }
        Check(RuntimeConfiguration.Quote("C:\\space folder\\") == "\"C:\\space folder\\\\\"", "Windows trailing separator quoting");
        string temporary = Path.Combine(Path.GetTempPath(), "HUD-config-" + Guid.NewGuid().ToString("N"));
        string savedHome = Environment.GetEnvironmentVariable("CODEX_HOME");
        string savedData = Environment.GetEnvironmentVariable("CODEX_TOKEN_HUD_HOME");
        try
        {
            Directory.CreateDirectory(Path.Combine(temporary, "python"));
            File.WriteAllText(Path.Combine(temporary, "python", "pythonw.exe"), "fixture placeholder");
            Environment.SetEnvironmentVariable("CODEX_HOME", Path.Combine(temporary, "custom codex"));
            Environment.SetEnvironmentVariable("CODEX_TOKEN_HUD_HOME", Path.Combine(temporary, "personal data"));
            var config = RuntimeConfiguration.Load(temporary);
            Check(config.Pythonw == Path.Combine(temporary, "python", "pythonw.exe"), "bundled Python is selected before PATH");
            Check(config.CodexHome == Path.Combine(temporary, "custom codex"), "CODEX_HOME override");
            Check(config.Layout.StartsWith(Path.Combine(temporary, "personal data")), "per-user layout storage");
            Json.Write(Path.Combine(temporary, "settings.json"), new Dictionary<string, object> {{"pythonw", "relative-pythonw.exe"}});
            config = RuntimeConfiguration.Load(temporary);
            Check(config.Pythonw == Path.Combine(temporary, "relative-pythonw.exe"), "relative Python override");
        }
        finally
        {
            Environment.SetEnvironmentVariable("CODEX_HOME", savedHome);
            Environment.SetEnvironmentVariable("CODEX_TOKEN_HUD_HOME", savedData);
            Directory.Delete(temporary, true);
        }
        Console.WriteLine("Presentation checks passed: " + checks);
    }
}

using System;
using System.Diagnostics;
using System.Runtime.InteropServices;

// This diagnostic only sends messages to our own status window.
class VerifyHud
{
    [StructLayout(LayoutKind.Sequential)] struct Rect { public int Left, Top, Right, Bottom; }
    [DllImport("user32.dll")] static extern bool SetProcessDpiAwarenessContext(IntPtr context);
    [DllImport("user32.dll", CharSet=CharSet.Unicode)] static extern IntPtr FindWindow(string cls, string title);
    [DllImport("user32.dll")] static extern uint GetWindowThreadProcessId(IntPtr h, out uint pid);
    [DllImport("user32.dll")] static extern bool GetWindowRect(IntPtr h, out Rect rect);
    [DllImport("user32.dll")] static extern IntPtr SendMessage(IntPtr h, uint message, IntPtr w, IntPtr l);
    [DllImport("user32.dll")] static extern bool SetWindowPos(IntPtr h, IntPtr after, int x, int y, int width, int height, uint flags);
    static int Hit(IntPtr h, int x, int y)
    { return SendMessage(h, 0x84, IntPtr.Zero, new IntPtr((y << 16) | (x & 0xffff))).ToInt32(); }
    static void Expect(string name, int actual, int wanted)
    {
        Console.WriteLine(name + "=" + actual + " expected=" + wanted);
        if (actual != wanted) Environment.Exit(2);
    }
    static void Main(string[] args)
    {
        SetProcessDpiAwarenessContext(new IntPtr(-4));
        IntPtr h = FindWindow(null, "Codex Token 状态条");
        if (h == IntPtr.Zero) { Console.WriteLine("HUD window not found"); Environment.Exit(1); }
        uint pid; GetWindowThreadProcessId(h, out pid);
        if (Process.GetProcessById((int)pid).ProcessName != "CodexTokenHud") Environment.Exit(3);
        Rect r; GetWindowRect(h, out r);
        int cx = (r.Left + r.Right) / 2, cy = (r.Top + r.Bottom) / 2;
        Expect("drag", Hit(h, cx, cy), 2);
        Expect("left", Hit(h, r.Left + 1, cy), 10);
        Expect("right", Hit(h, r.Right - 2, cy), 11);
        Expect("top", Hit(h, cx, r.Top + 1), 12);
        Expect("bottom", Hit(h, cx, r.Bottom - 2), 15);
        Expect("top-left", Hit(h, r.Left + 1, r.Top + 1), 13);
        Expect("top-right", Hit(h, r.Right - 2, r.Top + 1), 14);
        Expect("bottom-left", Hit(h, r.Left + 1, r.Bottom - 2), 16);
        Expect("bottom-right", Hit(h, r.Right - 2, r.Bottom - 2), 17);
        Expect("close-client", Hit(h, r.Right - 25, cy), 1);
        if (args.Length > 0 && args[0] == "move-resize")
        {
            SendMessage(h, 0x231, IntPtr.Zero, IntPtr.Zero);
            if (!SetWindowPos(h, IntPtr.Zero, r.Left + 40, r.Top - 90, 1260, 72, 0x0014)) Environment.Exit(4);
            SendMessage(h, 0x232, IntPtr.Zero, IntPtr.Zero);
            GetWindowRect(h, out r);
            Console.WriteLine("layout=" + r.Left + "," + r.Top + "," + (r.Right - r.Left) + "," + (r.Bottom - r.Top));
        }
    }
}

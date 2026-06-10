using System;
using System.Diagnostics;
using System.IO;
using System.Reflection;
using System.Windows.Forms;

internal static class InstallerStub
{
    [STAThread]
    private static int Main()
    {
        try
        {
            string appDir = Path.Combine(
                Environment.GetFolderPath(Environment.SpecialFolder.ProgramFiles),
                "ArezOne"
            );
            string exePath = Path.Combine(appDir, "AREZONE.exe");

            Directory.CreateDirectory(appDir);
            using (Stream input = Assembly.GetExecutingAssembly().GetManifestResourceStream("AREZONE.exe"))
            {
                if (input == null)
                {
                    throw new InvalidOperationException("No se encontro AREZONE.exe dentro del instalador.");
                }

                using (FileStream output = File.Create(exePath))
                {
                    input.CopyTo(output);
                }
            }

            CreateShortcut(
                Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.DesktopDirectory), "AREZONE.lnk"),
                exePath
            );

            string startFolder = Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.Programs), "AREZONE");
            Directory.CreateDirectory(startFolder);
            CreateShortcut(Path.Combine(startFolder, "AREZONE.lnk"), exePath);

            MessageBox.Show(
                "AREZONE fue instalado correctamente.",
                "Instalador AREZONE",
                MessageBoxButtons.OK,
                MessageBoxIcon.Information
            );

            Process.Start(exePath);
            return 0;
        }
        catch (Exception ex)
        {
            MessageBox.Show(
                "No se pudo instalar AREZONE:\n\n" + ex.Message,
                "Instalador AREZONE",
                MessageBoxButtons.OK,
                MessageBoxIcon.Error
            );
            return 1;
        }
    }

    private static void CreateShortcut(string shortcutPath, string targetPath)
    {
        Type shellType = Type.GetTypeFromProgID("WScript.Shell");
        if (shellType == null)
        {
            return;
        }

        object shell = Activator.CreateInstance(shellType);
        object shortcut = shellType.InvokeMember(
            "CreateShortcut",
            BindingFlags.InvokeMethod,
            null,
            shell,
            new object[] { shortcutPath }
        );

        Type shortcutType = shortcut.GetType();
        shortcutType.InvokeMember("TargetPath", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath });
        shortcutType.InvokeMember("WorkingDirectory", BindingFlags.SetProperty, null, shortcut, new object[] { Path.GetDirectoryName(targetPath) });
        shortcutType.InvokeMember("Description", BindingFlags.SetProperty, null, shortcut, new object[] { "AREZONE POS" });
        shortcutType.InvokeMember("IconLocation", BindingFlags.SetProperty, null, shortcut, new object[] { targetPath + ",0" });
        shortcutType.InvokeMember("Save", BindingFlags.InvokeMethod, null, shortcut, null);
    }
}

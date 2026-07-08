using System.Reflection;
using Autodesk.Revit.UI;
using MyRevitAddin.Commands;
using MyRevitAddin.Infrastructure;

namespace MyRevitAddin
{
    /// <summary>
    /// IExternalApplication: runs once at Revit startup. Builds the ribbon and wires up commands.
    /// There is no active document here — you get a UIControlledApplication, not a UIApplication,
    /// so you cannot touch a model in OnStartup.
    /// </summary>
    public class App : IExternalApplication
    {
        private const string TabName = "My Addin";

        public Result OnStartup(UIControlledApplication app)
        {
            // CreateRibbonTab throws if the tab already exists — guard it.
            try { app.CreateRibbonTab(TabName); } catch { /* tab already exists */ }

            // Reuse the panel if present (idempotent across add-in reloads), else create it.
            RibbonPanel panel = app.GetRibbonPanels(TabName).FirstOrDefault(p => p.Name == "Examples")
                                ?? app.CreateRibbonPanel(TabName, "Examples");

            Assembly asm = Assembly.GetExecutingAssembly();
            string asmPath = asm.Location;

            AddButton(panel, asm, asmPath, "cmdHello", "Hello\nRevit",
                typeof(HelloCommand).FullName!, "Show a Hello dialog.");

            AddButton(panel, asm, asmPath, "cmdCount", "Count\nElements",
                typeof(CountElementsCommand).FullName!, "Count walls/doors/windows (read-only).");

            AddButton(panel, asm, asmPath, "cmdLevels", "Create\nLevels",
                typeof(CreateLevelsCommand).FullName!, "Create levels at 3/6/9 m (transaction demo).");

            return Result.Succeeded;
        }

        public Result OnShutdown(UIControlledApplication app) => Result.Succeeded;

        private static void AddButton(RibbonPanel panel, Assembly asm, string asmPath, string name,
                                      string text, string className, string tooltip)
        {
            var data = new PushButtonData(name, text, asmPath, className) { ToolTip = tooltip };
            // Icons are optional. Drop icon32.png / icon16.png into Resources\ to show them.
            // Pass the assembly that embeds the PNGs (here, the add-in itself).
            data.LargeImage = ImageUtils.Load(asm, "icon32.png");
            data.Image = ImageUtils.Load(asm, "icon16.png");
            panel.AddItem(data);
        }
    }
}

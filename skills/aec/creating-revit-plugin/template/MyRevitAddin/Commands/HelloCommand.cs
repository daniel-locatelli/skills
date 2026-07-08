using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace MyRevitAddin.Commands
{
    /// <summary>
    /// Simplest possible command. [Transaction(TransactionMode.Manual)] is MANDATORY on every
    /// IExternalCommand — without it Revit fails to load the command.
    /// </summary>
    [Transaction(TransactionMode.Manual)]
    public class HelloCommand : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            // Object model: UIApplication -> UIDocument (UI/selection) -> Document (model database).
            UIDocument uidoc = commandData.Application.ActiveUIDocument;
            Document doc = uidoc.Document;

            TaskDialog.Show("Hello", $"Hello, Revit!\nActive document: {doc.Title}");
            return Result.Succeeded;
        }
    }
}

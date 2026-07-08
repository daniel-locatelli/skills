using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace MyRevitAddin.Commands
{
    /// <summary>
    /// Read-only query demo. TransactionMode.ReadOnly forbids any model modification —
    /// use it for report/inspect commands. Shows FilteredElementCollector usage.
    /// </summary>
    [Transaction(TransactionMode.ReadOnly)]
    public class CountElementsCommand : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            Document doc = commandData.Application.ActiveUIDocument.Document;

            int Count(BuiltInCategory cat) => new FilteredElementCollector(doc)
                .OfCategory(cat)
                .WhereElementIsNotElementType()   // placed instances, not type definitions
                .GetElementCount();

            int walls = Count(BuiltInCategory.OST_Walls);
            int doors = Count(BuiltInCategory.OST_Doors);
            int windows = Count(BuiltInCategory.OST_Windows);

            TaskDialog.Show("Element Count",
                $"Walls: {walls}\nDoors: {doors}\nWindows: {windows}");
            return Result.Succeeded;
        }
    }
}

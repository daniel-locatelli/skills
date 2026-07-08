using Autodesk.Revit.Attributes;
using Autodesk.Revit.DB;
using Autodesk.Revit.UI;

namespace MyRevitAddin.Commands
{
    /// <summary>
    /// Model-edit demo. Demonstrates the four things almost every productive command does:
    ///   1. Wrap edits in a Transaction (required — editing outside one throws).
    ///   2. Convert UI units -> internal units (Revit stores lengths in decimal FEET).
    ///   3. Be idempotent: re-running must not create duplicates (get-or-create by elevation).
    ///   4. Handle cancellation / failure cleanly via the Result enum.
    /// </summary>
    [Transaction(TransactionMode.Manual)]
    public class CreateLevelsCommand : IExternalCommand
    {
        public Result Execute(ExternalCommandData commandData, ref string message, ElementSet elements)
        {
            Document doc = commandData.Application.ActiveUIDocument.Document;

            // Levels to ensure exist, in metres (the UI/boundary unit).
            double[] metres = { 3.0, 6.0, 9.0 };

            // Existing level elevations (internal units = feet), for idempotency.
            var existing = new FilteredElementCollector(doc)
                .OfClass(typeof(Level))
                .Cast<Level>()
                .Select(l => l.Elevation)
                .ToList();

            try
            {
                int created = 0;
                using (var t = new Transaction(doc, "Create Levels"))
                {
                    t.Start();
                    foreach (double m in metres)
                    {
                        double feet = UnitUtils.ConvertToInternalUnits(m, UnitTypeId.Meters);
                        // Skip if a level already sits at ~this elevation (idempotent).
                        if (existing.Any(e => Math.Abs(e - feet) < 1e-6)) continue;

                        Level level = Level.Create(doc, feet);
                        level.Name = $"Level +{m:0.##} m";
                        created++;
                    }
                    t.Commit();
                }

                TaskDialog.Show("Create Levels",
                    created == 0 ? "All levels already exist — nothing to do."
                                 : $"Created {created} level(s).");
                return Result.Succeeded;
            }
            catch (Autodesk.Revit.Exceptions.OperationCanceledException)
            {
                return Result.Cancelled;
            }
            catch (Exception ex)
            {
                message = ex.Message;   // shown to the user by Revit
                return Result.Failed;
            }
        }
    }
}

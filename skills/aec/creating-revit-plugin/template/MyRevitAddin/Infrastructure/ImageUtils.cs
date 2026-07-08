using System.Reflection;
using System.Windows.Media.Imaging;

namespace MyRevitAddin.Infrastructure
{
    /// <summary>
    /// Loads ribbon icons from embedded resources. In .NET 8 add-ins, naive WPF pack URIs
    /// ("pack://application:,,,/...") frequently fail to render — loading from the embedded
    /// resource stream into a frozen BitmapImage is the reliable approach.
    /// Returns null if the resource isn't found, so buttons simply render without an icon.
    ///
    /// Pass the assembly that actually embeds the PNGs (usually
    /// <c>Assembly.GetExecutingAssembly()</c> from the add-in). Taking it as a parameter — rather
    /// than calling GetExecutingAssembly() inside here — keeps this working when ImageUtils is
    /// factored into a shared library whose assembly does not contain the icons.
    /// </summary>
    public static class ImageUtils
    {
        public static BitmapImage? Load(Assembly asm, string fileNameEndsWith)
        {
            try
            {
                string? resource = asm.GetManifestResourceNames()
                    .FirstOrDefault(n => n.EndsWith(fileNameEndsWith, StringComparison.OrdinalIgnoreCase));
                if (resource == null) return null;

                using var stream = asm.GetManifestResourceStream(resource);
                if (stream == null) return null;

                var img = new BitmapImage();
                img.BeginInit();
                img.CacheOption = BitmapCacheOption.OnLoad;  // read fully before the stream closes
                img.StreamSource = stream;
                img.EndInit();
                img.Freeze();                                 // thread-safe + faster
                return img;
            }
            catch
            {
                return null;
            }
        }
    }
}

# Resources

Drop ribbon icons here as PNG files. Recommended sizes:

- `icon32.png` — 32×32, used for `PushButtonData.LargeImage`
- `icon16.png` — 16×16, used for `PushButtonData.Image`

`MyRevitAddin.csproj` embeds every `Resources\*.png` as an `EmbeddedResource`, and
`Infrastructure/ImageUtils.cs` loads them by filename at runtime. If no matching icon is
found, the button simply renders without one (no error). This folder may stay empty.

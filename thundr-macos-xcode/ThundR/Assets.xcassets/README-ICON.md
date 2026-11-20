# App icon — drop ThundR art here

Add the ThundR avatar (purple thunder imp, red horns, bat wings, yellow
lightning bolt tail) as PNG files into `AppIcon.appiconset/` at the sizes
in `Contents.json` (16, 32, 128, 256, 512, @1x and @2x).

Source: the ThundR botcard package — `ThundR-profile.webp` /
`ThundR-profile-darkmode.webp` (convert to PNG for Xcode).

Also add a `ThundR` image set to `Assets.xcassets/` (the sidebar in
ContentView.swift uses `Image("ThundR")`). The project builds without
these images; the sidebar avatar will simply be blank until added.

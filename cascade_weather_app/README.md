# Cascade Mountain Weather - iOS App

A native iOS app that wraps the Cascade Mountain Weather website with push notification support.

## What is This?

This is a Flutter-based iOS app that:

1. **Displays your website** in a native WebView
2. **Sends push notifications** when there are mountain weather updates
3. **Works offline** (with cached content from PWA)
4. **Handles deep links** to specific forecast posts or current weather

## Quick Start

### Prerequisites
- macOS with Xcode installed
- Flutter SDK (already in `~/Development/flutter/`)
- Apple Developer account (for App Store distribution)

### Run the App

```bash
# Set up Flutter path
export PATH="$PATH:$HOME/Development/flutter/bin"

# Navigate to app directory
cd cascade_weather_app

# Run on iOS simulator
flutter run -d "iPhone 15"
```

### Build for App Store

See [FLUTTER_SETUP.md](FLUTTER_SETUP.md) for complete build instructions.

## Project Structure

```
lib/
├── main.dart              # Firebase initialization, push notifications, WebView
└── firebase_options.dart  # Firebase configuration (needs real credentials)

ios/
├── Runner.xcworkspace     # Main Xcode project
├── Podfile                # iOS dependencies
└── Runner/
    ├── Info.plist
    └── GoogleService-Info.plist  # (Add from Firebase)
```

## Key Features

### Push Notifications
- Uses Firebase Cloud Messaging (FCM)
- Local notification display with alerts
- Tap-to-open handling
- Background message processing

### WebView Integration
- Loads full website
- JavaScript enabled
- Offline detection with banner
- Same PWA features as web version

### Native iOS Features
- Home screen icon
- Launch screen
- App switcher preview
- Notification badge

## Setup Checklist

- [ ] Create Firebase project
- [ ] Download GoogleService-Info.plist
- [ ] Add .plist to Xcode project
- [ ] Update firebase_options.dart with real credentials
- [ ] Enable Push Notifications capability in Xcode
- [ ] Update iOS Deployment Target to 12.0+
- [ ] Test on simulator: `flutter run`
- [ ] Test push notifications via Firebase Console

## Dependencies

- **firebase_core** - Firebase backend SDK
- **firebase_messaging** - Cloud messaging / push notifications
- **flutter_local_notifications** - Local notification display
- **webview_flutter** - WebView for displaying website
- **http** - HTTP requests

## Common Commands

```bash
# Add Flutter to PATH (run each session)
export PATH="$PATH:$HOME/Development/flutter/bin"

# Hot reload while running (fast iteration)
r

# Full restart
R

# View logs
flutter logs

# Clean build
flutter clean && flutter pub get

# List available devices
flutter devices

# Run on specific device
flutter run -d "device_id"

# Analyze code
flutter analyze

# Format code
dart format lib/
```

## Next Steps

1. **Configure Firebase**: Follow [FLUTTER_SETUP.md](FLUTTER_SETUP.md) Step 1-3
2. **Test Locally**: Run `flutter run` and verify WebView loads
3. **Send Test Notification**: Use Firebase Console to send test push message
4. **Prepare for App Store**: Build release version (see FLUTTER_SETUP.md)
5. **Automate Updates**: Set up CI/CD to build & deploy on code changes

## Debugging Push Notifications

Enable Firebase debugging:
```dart
// In lib/main.dart, after Firebase.initializeApp():
await FirebaseMessaging.instance.setAutoInitEnabled(true);
```

View FCM Token (needed for manual testing):
```dart
final token = await FirebaseMessaging.instance.getToken();
print('FCM Token: $token');
```

## Documentation Links

- [Flutter Docs](https://flutter.dev/docs)
- [Firebase for Flutter](https://firebase.flutter.dev/)
- [WebView Flutter](https://pub.dev/packages/webview_flutter)
- [Local Notifications](https://pub.dev/packages/flutter_local_notifications)

## File Modification Guide

Want to change something? Here are the key files:

| Change | File |
|--------|------|
| App title, colors, theme | `lib/main.dart` → `MyApp` class |
| Website URL to load | `lib/main.dart` → `WebView` initialUrl |
| Firebase project ID | `lib/firebase_options.dart` |
| App name on home screen | `ios/Runner/Info.plist` → CFBundleDisplayName |
| App icon | Replace files in `ios/Runner/Assets.xcassets` |
| First screen/splash | `ios/Runner/Assets.xcassets/LaunchImage.imageset` |

## Troubleshooting

**App won't build?**
```bash
cd ios
rm -rf Pods Podfile.lock
cd ..
flutter clean
flutter pub get
flutter run
```

**Push notifications not appearing?**
- Check GoogleService-Info.plist is in Xcode
- Verify Firebase project settings
- Test with Firebase Console Cloud Messaging tab

**WebView shows blank screen?**
- Check internet connection
- Verify URL is correct (currently: cascademountainweather.com)
- Check app has network permissions

## Development Workflow

1. Make changes to Dart code
2. Press `r` in terminal for hot reload
3. Changes appear instantly in app
4. For iOS-specific changes, restart with `R`

## Ready to Deploy?

1. Follow [FLUTTER_SETUP.md](FLUTTER_SETUP.md) - "Building for App Store" section
2. Create certificates and provisioning profiles in Apple Developer
3. Build release: `flutter build ios --release`
4. Upload via Xcode or Apple Transporter
5. Submit for review in App Store Connect

For any issues, check FLUTTER_SETUP.md for detailed troubleshooting.

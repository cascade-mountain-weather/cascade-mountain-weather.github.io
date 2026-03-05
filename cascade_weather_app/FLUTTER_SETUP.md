# Flutter iOS App Setup Guide

This Flutter app wraps your Cascade Mountain Weather website with native iOS push notifications.

## Architecture

```
cascade_weather_app/
├── lib/
│   ├── main.dart              # Firebase init + WebView + Push notification handling
│   └── firebase_options.dart  # Firebase config (stub - needs real credentials)
├── ios/                       # Native iOS code
└── pubspec.yaml              # Dependencies: Firebase, local notifications, WebView
```

## Setup Steps

### 1. Firebase Project Setup

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create new project or use existing: `cascade-weather-app`
3. Add iOS app with:
   - iOS Bundle ID: `com.cascademountainweather.app`
   - App Name: `Cascade Mountain Weather`
4. Download `GoogleService-Info.plist`
5. Add the `.plist` file to Xcode:
   - Open `ios/Runner.xcworkspace` (NOT .xcodeproj)
   - Drag `GoogleService-Info.plist` into Runner folder
   - Check "Copy items if needed"

### 2. Update Firebase Configuration

Edit `lib/firebase_options.dart` with real credentials from Firebase Console:
```dart
return const FirebaseOptions(
  apiKey: 'AIzaSy...',           // From GoogleService-Info.plist
  appId: '1:123456789:ios:...',  // App ID from plist
  messagingSenderId: '123456789',
  projectId: 'cascade-weather-app',
  iosBundleId: 'com.cascademountainweather.app',
);
```

### 3. Enable Push Notifications in Xcode

1. Open: `ios/Runner.xcworkspace`
2. Select "Runner" → Signing & Capabilities
3. Click "+ Capability" → Search "Push Notifications"
4. Add Push Notifications capability
5. Select Team (your Apple Developer account)

### 4. Configure Firebase Messaging in iOS

1. In Xcode: Runner → Build Settings
2. Search: "Enable Bitcode"
3. Set to: `No`
4. Select "Runner" → Info tab
5. Scroll to "Deployment Info" → Minimum Deployment: `11.0` or higher

### 5. Podfile Configuration (Important for iOS)

Edit `ios/Podfile`:
```ruby
# Add this at the top if not present:
platform :ios, '12.0'  # Minimum iOS version

post_install do |installer|
  # Add Firebase specific pod fixes
  installer.pods_project.targets.each do |target|
    flutter_additional_ios_build_settings(target)
  end
end
```

### 6. Run the App

```bash
# Add Flutter to PATH (if not already done)
export PATH="$PATH:$HOME/Development/flutter/bin"

# Navigate to project
cd /Users/clintonalden/Documents/personal/wx_website/cascade_weather_app

# Clean and get fresh build
flutter clean
flutter pub get

# Run on iOS simulator
flutter run -d "iPhone 15"

# Or build for real device
flutter run -d (device-id)  # Find with: flutter devices
```

## Development Workflow

### Hot Reload
While app is running:
```bash
r     # Hot reload (Dart code changes)
R     # Hot restart (full app restart)
```

### Key Files to Modify

- **lib/main.dart**: App logic, push notification handlers, WebView configuration
- **lib/firebase_options.dart**: Firebase credentials
- **pubspec.yaml**: Add new dependencies (e.g., `flutter pub add package_name`)

### Testing Push Notifications

1. Firebase Console → Cloud Messaging → Create Campaign
2. Select "Cascade Weather App" (iOS target)
3. Create test message → Send to test devices
4. Check that notification appears on device/simulator

## Building for App Store

### Preparation

1. Create Apple Developer account if not already done
2. Create App ID in Apple Developer Portal
3. Create provisioning profiles (Development & Distribution)
4. Create App in App Store Connect

### Build Steps

```bash
# Build iOS app for distribution
flutter build ios --release

# Or build to produce .ipa file directly
flutter build ios --release
cd ios
xcodebuild -workspace Runner.xcworkspace -scheme Runner -configuration Release -derivedDataPath build

# Upload to App Store via Xcode or Transporter
```

## Next Steps

1. **Configure Real-Time Data Push**: Modify your backend to send FCM messages when weather alerts occur
2. **Create Notification Campaign**: Use Firebase Console to test sending messages to users
3. **Design App Icon**: Replace default Flutter icon with CMW logo
4. **Add Offline Sync**: Implement local caching for weather data using Hive or SQLite
5. **Analytics**: Enable Firebase Analytics in this app

## Troubleshooting

**"Build failed: Pod install error"**
```bash
cd ios
rm -rf Pods Podfile.lock
cd ..
flutter pub get
flutter run
```

**"Push notifications not working"**
- Verify `GoogleService-Info.plist` is added to Xcode project
- Check iOS version is 11.0+
- Ensure capabilities are enabled
- Check Firebase console shows app is registered

**"WebView not loading website"**
- Verify internet connectivity
- Check URL is correct in `main.dart` (currently: `https://www.cascademountainweather.com`)
- Allow insecure connections if testing with http: Edit `Info.plist` → Add NSAppTransportSecurity

## File Structure Quick Reference

```
cascade_weather_app/
├── lib/
│   ├── main.dart                    # App entry, Firebase init, push handler
│   └── firebase_options.dart        # Firebase credentials
├── ios/
│   ├── Runner.xcworkspace           # (Use this, not .xcodeproj)
│   ├── Runner/
│   │   ├── Info.plist               # iOS app configuration
│   │   └── GoogleService-Info.plist # (Add this from Firebase)
│   └── Podfile                       # iOS dependency management
├── android/                         # (For future Android build)
├── pubspec.yaml                     # Flutter dependencies
└── FLUTTER_SETUP.md                 # This file
```

## Useful Commands

```bash
# Add Flutter to PATH
export PATH="$PATH:$HOME/Development/flutter/bin"

# Check Flutter installation
flutter --version
flutter doctor

# Device management
flutter devices
flutter attach -d (device-id)

# Build variants
flutter run -d "iPhone 15"              # Run on simulator
flutter run --release                   # Production build
flutter build ios --release             # Build for App Store

# Debugging
flutter logs
flutter run -v                          # Verbose logging
```

## Firebase Cloud Messaging (FCM) for Push Notifications

### Sending Messages from Backend

Your Python backend (or any service) can send push notifications:

```python
from firebase_admin import messaging

# Send to all iOS devices with topic subscription
message = messaging.Message(
    notification=messaging.Notification(
        title='Mountain Weather Alert',
        body='New snow forecast for Stevens Pass!',
    ),
    data={
        'forecast_type': 'snow',
        'location': 'stevens_pass',
        'depth_inches': '12-18',
    },
    topic='weather_alerts',  # Or specific device token
)

response = messaging.send(message)
print(f'Successfully sent message: {response}')
```

Subscribe to topics in the app:
```dart
// In lib/main.dart, add to _setupPushNotifications():
await FirebaseMessaging.instance.subscribeToTopic('weather_alerts');
```

## Next Developer Session

To continue development:

1. Set PATH: `export PATH="$PATH:$HOME/Development/flutter/bin"`
2. Open project: `cd cascade_weather_app`
3. Run: `flutter run -d "iPhone 15"` (or other device)
4. Edit code → Hot reload with `r`

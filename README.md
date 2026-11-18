
<img width="1920" height="1080" alt="blender_universal_transform_gizmo" src="https://github.com/user-attachments/assets/0d9665cc-3241-4801-a06a-0dc94728da99" />

# Universal Transform Gizmo

Vastly improved transform gizmo (widget) for Blender 5.2+

Design improvements inspired by [SDF Modeler](https://sascha-rode.itch.io/sdf-modeler), [MagicaCSG](https://www.patreon.com/c/magicavoxel), Unreal Engine!

## 👁️ Improvements over default gizmo
* One gizmo to rule them all. No need to switch gizmo modes.
* Gizmo controls always face the viewer.
* Both single and double sided transform arrows.
* Optional real time unit display near gizmo.
* Optional orientation toggles near gizmo (global, local, etc).
* Highly customizable with many visual tweak options.


<img width="439" height="300" alt="gizmo_hype" src="https://github.com/user-attachments/assets/11543e88-fc1b-465b-9eb6-d70bb1930dbd" />


## 📥 Install

### Automatic: Install `.zip` directly.

📥 [Download current main from Github](https://github.com/gnat/blender_universal_transform_gizmo/archive/refs/heads/main.zip)

Start Blender ➡️ Edit ➡️ Preferences ... ➡️ Get Extensions ➡️ Install From Disk... ➡️ Choose the `.zip`

Universal Transform Gizmo will install and activate automatically. ✅

<img width="778" height="364" alt="install_good" src="https://github.com/user-attachments/assets/77e74313-edff-48cf-8968-7a4dcf5d8dc6" />


### Manual: Add to your extensions folder.

📥 [Download current main from Github](https://github.com/gnat/blender_universal_transform_gizmo/archive/refs/heads/main.zip)

Copy the contained `blender_universal_transform_gizmo-main` to your extensions folder:

* Windows: `%APPDATA%\Blender Foundation\Blender\5.3\extensions\user_default`
* Linux: `~/.config/blender/5.3/extensions/user_default`
* MacOS: `~/Library/Application Support/Blender/5.3/extensions/user_default`

Rename from `blender_universal_transform_gizmo-main` to `universal_transform_gizmo`

Start Blender ➡️ Edit ➡️ Preferences ... ➡️ Add-ons ➡️ Universal Transform Gizmo ✅

## Useful Tips

Toggle the sidebar to see the gizmo tweak panel.

<img width="292" height="243" alt="arrow_good" src="https://github.com/user-attachments/assets/c43cde70-9ab3-4000-8f6c-267249891738" />

Gizmo quick hide.

<img width="202" height="186" alt="toggle_good" src="https://github.com/user-attachments/assets/fd800be1-19f4-4563-ab53-c5c53151d229" />

## 📚️ Design References

[SDF Modeler](https://sascha-rode.itch.io/sdf-modeler) by Sascha Rode

<img width="421" height="399" alt="image" src="https://github.com/user-attachments/assets/1f55db79-189d-4d27-91a9-d2f52fbc3f12" />

[MagicaCSG](https://www.patreon.com/c/magicavoxel) by ephtracy

<img width="453" height="423" alt="image" src="https://github.com/user-attachments/assets/87da42a1-ccb2-428b-ba15-5f1d93c450f9" />

## 🌘 Change Log

### 1.4.0

* New Trackball Rotation control (Arcball) with 2 axis visual.
* Special thanks YAZZ for all the testing!

### 1.3.1

* Hide when built in gizmos are explicitly selected.
* Better defaults.
* Special thanks YAZZ for all the testing!

### 1.3.0

* New filter for Transform Pivot Point toggle. (Optional)
* Fix issue with Adjust Last Operation panel.
* Better defaults.
* Special thanks YAZZ for all the testing!

### 1.2.0

* Transform Mode toggles now easily customized.
* Show/hide can now be added to Blender Quick Favorites.
* Improved polish for use with Chisel extension.
* Options menu cleanup.
* Special thanks YAZZ for all the testing!

### 1.1.0

* New show/hide keybind. (Optional)
* New show/hide button. (Optional)
* New assortment of Transform Mode toggles. (Optional)
* Fixes for use with Chisel extension.
* Better defaults.
* Decreased Blender requirement to 5.2.0
* Special thanks YAZZ for all the testing!

### 1.0.0

* Initial public release.

## FAQ

What happened to the Blender `/scripts/addons` folder?
* Blender deprecated the legacy add-on format in 4.2, but still supports loading it.


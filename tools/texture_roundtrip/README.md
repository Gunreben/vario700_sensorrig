# Colouring the URDF meshes

There are two ways to colour the visual meshes. Both keep the geometry, link
frames and URDF scales exactly as they are.

- **Flat paint (recommended):** gives each mesh piece a plain colour from a
  palette. The colours are guessed automatically and you fix them by hand.
  No textures are needed.
- **AI texture round trip:** see below. It gave poor results on this model.

Both start with `assemble.py` (step 1 below).

## Flat paint

```bash
blender -b -P tools/texture_roundtrip/paint_auto.py -- --preview
blender texture_work/paint.blend          # fix colours by hand (optional)
blender -b -P tools/texture_roundtrip/paint_export.py -- \
    --urdf urdf/vario700_sensorrig_msa.urdf urdf/vario700_sensorrig_manual.urdf
```

`paint_auto.py` gives every loose piece a palette material. Wheels are
split by radius (tyre/rim). Body pieces are classified by position, size and
flatness. The rules live in `classify_body()` and the colours in `PALETTE`.
Check the result in `texture_work/paint_*.png`.

To fix a piece in Blender:
1. Select a link and press Tab for edit mode, then 3 for face select.
2. Hover over the piece and press L to select it.
3. In the Material tab, pick the colour and click **Assign**. Save with Ctrl+S.

Use Solid shading with the Color set to *Material* to see the colours.

`paint_export.py` writes `meshes/painted/<link>_visuals.obj|.mtl` with plain
sRGB colours. It also writes a `<name>_painted.urdf` copy of every URDF
passed with `--urdf`, where only the `<visual>` meshes change.

Note: rerunning `paint_auto.py` overwrites your manual fixes in `paint.blend`.

# AI texture round trip

Merges the per-link visual meshes into one model for an AI texturing tool
(e.g. 3daistudio.com Texture Generator). It then bakes the result back onto
the original per-link meshes, so the geometry, link frames and URDF scales
stay the same.

Needs Blender ≥ 4.2; tested with 5.2 in `~/opt`, linked as `~/.local/bin/blender`.

## 1. Assemble (needed for both)

```bash
blender -b -P tools/texture_roundtrip/assemble.py -- \
    --urdf urdf/vario700_sensorrig_manual.urdf --preview
```

- `texture_work/upload.glb`: upload this file (~26 MB, full resolution).
  Use `--decimate 0.5` if the tool rejects it.
- `texture_work/preview.png`: check that all parts are in place.

## 2. Texture

Use the tool's texture-only mode, not image/text-to-3D. Download the result
as GLB.

## 3. Bake back

```bash
blender -b -P tools/texture_roundtrip/bake_back.py -- \
    --textured ~/Downloads/<result>.glb --preview
```

- `meshes/textured/<link>_visuals.obj|.mtl` and `<link>_albedo.png`
- `urdf/vario700_sensorrig_manual_textured.urdf`: the `<visual>` meshes point
  at the textured files; collision meshes are unchanged.
- `texture_work/textured_preview.png`: quick check.

The script transfers colour by ray casting, so the tool is free to remesh,
recentre or rescale the model. It fits the bounding box back automatically
(`--align bbox`). If the log warns about a non-uniform extent ratio, the tool
rotated the model. In that case, open `texture_work/bake_scene.blend`, fix the
pose of `ai_textured`, export it, and rerun with `--align none`.

Grey areas in the albedo mean no colour was found within `--max-dist`
(default 0.1 m). Raise `--max-dist` or `--cage` if large regions stay grey.
Texture size: `--res` (default 4096 for parts over 4 m, otherwise 2048).

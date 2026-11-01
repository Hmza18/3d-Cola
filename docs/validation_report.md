# Elo Cola -- validation report

Blender **5.2.3 LTS** &nbsp;|&nbsp; **10/10 tests passed**

### Test 1 &mdash; Required files exist and are non-empty

**PASS**

| | check | detail |
|---|---|---|
| PASS | assets/elo_cola.obj | `2,902,513 bytes` |
| PASS | assets/elo_cola.mtl | `281 bytes` |
| PASS | assets/elo_cola_texture.png | `909,075 bytes` |
| PASS | assets/elo_cola.blend | `1,701,419 bytes` |
| PASS | renders/elo_cola_product_512.png | `266,419 bytes` |

### Test 2 &mdash; The asset contains exactly one mesh object

**PASS**

| | check | detail |
|---|---|---|
| PASS | elo_cola.blend holds exactly 1 mesh object | `1: ['EloCola']` |
| PASS | every other object is a camera or a light (not exported) | `['CAMERA', 'LIGHT', 'MESH']` |
| PASS | elo_cola.obj declares exactly 1 object | `['EloCola']` |
| i | cameras / lights in the project | `['ProductCam'] / ['FillPanel', 'FrontBounce', 'KeyPanel', 'LidFill', 'RimLeft', 'RimRight', 'TopPanel']` |

### Test 3 &mdash; The exported model references exactly one PNG texture

**PASS**

| | check | detail |
|---|---|---|
| PASS | MTL references exactly one image file | `['elo_cola_texture.png']` |
| PASS | that image is a PNG | `elo_cola_texture.png` |
| PASS | the image sits beside the OBJ/MTL | `assets/elo_cola_texture.png` |
| PASS | MTL declares exactly one material | `['EloColaSurface']` |
| PASS | .blend holds exactly one image datablock | `['elo_cola_texture']` |
| PASS | the material uses exactly one image-texture node | `['elo_cola_texture']` |
| PASS | texture is 2048x2048 | `2048x2048` |
| PASS | texture is packed inside the .blend | `{'name': 'elo_cola_texture', 'size': [2048, 2048], 'packed': True, 'filepath': '//assets/elo_cola_texture.png'}` |

### Test 4 &mdash; Geometry is closed on every side (watertight, manifold)

**PASS**

| | check | detail |
|---|---|---|
| PASS | zero boundary edges | `0` |
| PASS | zero non-manifold edges | `0` |
| PASS | zero loose vertices | `0` |
| PASS | zero loose edges | `0` |
| PASS | zero degenerate faces | `0` |
| PASS | zero non-manifold vertices | `0` |
| PASS | all faces consistently wound (orientable) | `0` |
| i | disconnected shells | `2` |
| PASS | shell 0 closed with outward normals | `V=19970 E=40064 F=20096 chi=2 genus=0 volume=382.9566 cm^3 open_edges=0` |
| PASS | shell 1 closed with outward normals | `V=768 E=1536 F=768 chi=0 genus=1 volume=0.0796 cm^3 open_edges=0` |

### Test 5 &mdash; Front label faces -Y and the can stands along +Z

**PASS**

| | check | detail |
|---|---|---|
| PASS | the can stands on z = 0 | `z_min=0.000000000` |
| PASS | +Z is the long axis | `z=12.2706 x=6.6000 y=6.6000` |
| PASS | circular in plan | `\|x-y\|=0.00e+00` |
| PASS | found loops at label u = 0.5 | `250` |
| PASS | label centre lies on the x = 0 plane | `max\|x\|=6.062e-16` |
| PASS | label centre points at -Y | `max y=-2.510000 cm` |
| i | pull-tab y extent (cm) | `-2.642 .. 2.642` |
| i | native bounding box (cm) | `6.6000 x 6.6000 x 12.2706` |
| PASS | raw OBJ text: found label-centre vertices | `202` |
| PASS | raw OBJ text: label centre lies on x = 0 | `max\|x\|=0.00e+00` |
| PASS | raw OBJ text: label centre faces -Y (file is not axis-converted) | `y -0.033000 .. -0.025100 m` |
| PASS | raw OBJ text: the can stands along +Z | `z 0.000000 .. 0.122706 m` |

### Test 6 &mdash; OBJ exported with scale factor 0.01, applied exactly once

**PASS**

| | check | detail |
|---|---|---|
| PASS | build manifest records global_scale = 0.01 | `0.01` |
| PASS | export used Blender's identity axis mapping (no axis rewrite) | `forward=Y up=Z` |
| PASS | exported/native dimension ratio is exactly 0.01 | `0.010000000  0.010000000  0.010000032` |
| PASS | object transform scale is 1.0 (0.01 is NOT applied twice) | `(1.0, 1.0, 1.0)` |
| PASS | exported mesh still stands on z = 0 | `0.000000000` |
| i | native dimensions (Blender units = cm) | `6.6000 x 6.6000 x 12.2706` |
| i | exported OBJ dimensions (metres) | `0.066000 x 0.066000 x 0.122706` |
| i | i.e. real-world size | `66.0 x 66.0 x 122.7 mm` |

### Test 7 &mdash; UV mapping is valid, correctly routed and not mirrored

**PASS**

| | check | detail |
|---|---|---|
| PASS | exactly one UV layer | `['UVMap']` |
| PASS | all UV coordinates are finite (no NaN/inf) | |
| PASS | all UVs inside [0, 1] | `u 0.000000..1.000000  v 0.085000..1.000000` |
| PASS | every face lands inside a declared atlas region | `0 stray faces` |
| PASS | atlas regions do not overlap each other | `0` |
| i | faces per region | `label=8064, lid=4480, bottom=4736, tab_top=96, tab_bot=96, tab_wall=576, rim=2816` |
| PASS | exact test: no two non-adjacent faces overlap in UV space | `0 overlapping pairs, total 0.000e+00, worst 0.000e+00 (atlas = 1.0)` |
| i | UV area used / non-adjacent triangle pairs tested | `0.76477 / 217,240` |
| PASS | found front-facing label faces to test | `798` |
| PASS | +u runs to +x on the front (artwork NOT mirrored) | `score=3192` |
| PASS | +v runs up the can (artwork not flipped) | `score=3192` |
| PASS | label faces sample saturated printed ink (not bare metal) | `mean channel spread 137.7, mean RGB [95.2, 58.1, 117.3]` |
| PASS | cobalt, red and white artwork all land on the barrel | `of 8064 label faces: 59.2% cobalt, 31.9% red, 9.0% white` |
| PASS | lid faces sample neutral aluminium | `mean RGB [179.0, 183.5, 190.0]` |
| PASS | bottom faces sample neutral aluminium | `mean RGB [170.4, 175.2, 182.2]` |
| PASS | rim faces sample neutral aluminium | `mean RGB [178.4, 182.6, 188.8]` |
| PASS | tab_top faces sample neutral aluminium | `mean RGB [209.0, 212.7, 218.1]` |

### Test 8 &mdash; Exported OBJ re-imports cleanly into an empty Blender scene

**PASS**

| | check | detail |
|---|---|---|
| PASS | exactly one mesh imported | `['EloCola']` |
| PASS | vertex count survives the round trip | `20738 vs 20738` |
| PASS | face count survives the round trip | `20864 vs 20864` |
| PASS | UV layer present | `['UVMap']` |
| PASS | material reference resolves | `['EloColaSurface']` |
| PASS | exactly one texture referenced | `['elo_cola_texture.png']` |
| PASS | texture file resolves on disk | `[]` |
| PASS | texture loads at full resolution | `[[2048, 2048]]` |
| PASS | dimensions are native x 0.01 (to the OBJ's 1e-6 m precision) | `[0.066, 0.066, 0.122706003] vs expected [0.065999999, 0.065999999, 0.122705603]` |
| PASS | re-import needs no corrective transform (identity axes) | `[[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0], [0.0, 0.0, 0.0, 1.0]]` |
| PASS | still standing on z = 0 | `0.0` |
| PASS | label centre still faces -Y after the round trip | `loops=202 max\|x\|=0.0 max_y=-0.0251` |
| PASS | geometry is still watertight after the round trip | `boundary=0 nonmanifold=0 loose=0 degenerate=0` |
| PASS | every shell still closed with outward normals | `[{'faces': 20096, 'volume': 0.000382954452, 'open_edges': 0}, {'faces': 768, 'volume': 7.9581e-08, 'open_edges': 0}]` |

### Test 9 &mdash; Saved .blend opens in a separate Blender process

**PASS**

| | check | detail |
|---|---|---|
| PASS | file opened without error | |
| PASS | one mesh object present | `['EloCola']` |
| PASS | UV map present | `['UVMap']` |
| PASS | material present | `['EloColaSurface']` |
| PASS | single texture present and packed (no missing dependency) | `[{'name': 'elo_cola_texture', 'size': [2048, 2048], 'packed': True, 'filepath': '//assets/elo_cola_texture.png'}]` |
| PASS | render set-up saved (Cycles) | `CYCLES` |
| PASS | camera and studio lights saved with the project | `1 camera(s), 7 light(s)` |

### Test 10 &mdash; Final product image is exactly 512 x 512 PNG

**PASS**

| | check | detail |
|---|---|---|
| PASS | format is PNG | `PNG` |
| PASS | resolution is 512 x 512 | `512 x 512` |
| PASS | image is not blank | `stddev=74.86` |
| i | file size | `266,419 bytes` |

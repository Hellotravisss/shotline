// shotline · Illustrator helpers for App Store slides (ExtendScript, Illustrator 2025+).
// #include this file from a build script, then: var S = Slides(doc, artboardIndex, device).
// See docs/ILLUSTRATOR.md for the workflow and the traps these helpers work around.
//
// Coordinates are top-left within the artboard, in px (1 pt = 1 px at 72 ppi export).

// Apple bezel PNGs (developer.apple.com/design/resources, "Product Bezels").
// sx/sy/sw/sh = the screen hole; it equals the simulator screenshot size, so a capture
// drops in at 1:1. r = screen corner radius in bezel px (the capture is clipped to it, or
// its square corners show past the device edge).
var SHOTLINE_DEVICES = {
  iphone: { W: 1320, H: 2868, bw: 1350, bh: 2760, sx: 72, sy: 69, sw: 1206, sh: 2622, r: 140 },  // iPhone 17 Pro bezel, 6.9" canvas
  ipad: { W: 2064, H: 2752, bw: 2300, bh: 3000, sx: 118, sy: 124, sw: 2064, sh: 2752, r: 40 }     // iPad Pro (M5) 13" bezel
};

function shotlineRGB(hex) { var c = new RGBColor(); c.red = parseInt(hex.substr(1, 2), 16); c.green = parseInt(hex.substr(3, 2), 16); c.blue = parseInt(hex.substr(5, 2), 16); return c; }

function Slides(doc, index, dev) {
  var ab = doc.artboards[index].artboardRect;
  function X(x) { return ab[0] + x; }
  function Y(y) { return ab[1] - y; }
  var S = { W: dev.W, H: dev.H, doc: doc };

  S.rect = function (x, y, w, h, fill, r) {
    var p = r ? doc.pathItems.roundedRectangle(Y(y), X(x), w, h, r, r) : doc.pathItems.rectangle(Y(y), X(x), w, h);
    p.stroked = false;
    if (fill) { p.filled = true; p.fillColor = (typeof fill === 'string') ? shotlineRGB(fill) : fill; } else { p.filled = false; }
    return p;
  };
  // stops: [[rampPoint 0–100, '#hex'], …]
  S.radial = function (stops) {
    var g = doc.gradients.add(); g.type = GradientType.RADIAL;
    while (g.gradientStops.length < stops.length) g.gradientStops.add();
    for (var i = 0; i < stops.length; i++) { g.gradientStops[i].color = shotlineRGB(stops[i][1]); g.gradientStops[i].rampPoint = stops[i][0]; g.gradientStops[i].midPoint = 50; }
    var gc = new GradientColor(); gc.gradient = g; return gc;
  };
  S.line = function (x1, y1, x2, y2, color, w) {
    var p = doc.pathItems.add(); p.setEntirePath([[X(x1), Y(y1)], [X(x2), Y(y2)]]);
    p.filled = false; p.stroked = true; p.strokeColor = shotlineRGB(color); p.strokeWidth = w || 2; return p;
  };
  S.dot = function (cx, cy, r, color) { var p = doc.pathItems.ellipse(Y(cy - r), X(cx - r), 2 * r, 2 * r); p.stroked = false; p.filled = true; p.fillColor = shotlineRGB(color); return p; };

  // Text in a very wide AREA box, so Illustrator aligns it. Point text is the trap: its
  // bounds read inside a script are stale until the frame next moves, so "measure and
  // centre" lands half a width off. x = left edge | centre | right edge (o.align); y = top.
  // Lines split on \r. o: align, leading, tracking (1/1000 em), opacity.
  S.text = function (str, x, y, font, size, color, o) {
    o = o || {};
    var BOX = 4000, lead = o.leading || Math.round(size * 1.18), n = str.split('\r').length;
    // Parenthesised on purpose: ExtendScript evaluates an unparenthesised nested ?: wrongly
    // ('center' came out as 'right'). Keep every nested ternary in parentheses.
    var left = (o.align === 'center') ? (x - BOX / 2) : ((o.align === 'right') ? (x - BOX) : x);
    var box = doc.pathItems.rectangle(Y(y), X(left), BOX, lead * n + size);
    var t = doc.textFrames.areaText(box); t.contents = str;
    var ca = t.textRange.characterAttributes;
    ca.textFont = app.textFonts.getByName(font); ca.size = size; ca.fillColor = shotlineRGB(color);
    ca.tracking = o.tracking || 0; ca.autoLeading = false; ca.leading = lead;
    t.textRange.paragraphAttributes.justification = (o.align === 'center') ? Justification.CENTER : ((o.align === 'right') ? Justification.RIGHT : Justification.LEFT);
    if (o.opacity) t.opacity = o.opacity;
    return t;
  };
  // Restyle the last occurrence of `tail` (e.g. raised cents: '.09' or ',09 $').
  S.styleTail = function (t, tail, a) {
    var from = t.contents.lastIndexOf(tail); if (from < 0) return;
    for (var i = from; i < from + tail.length; i++) {
      var c = t.characters[i].characterAttributes;
      if (a.color) c.fillColor = shotlineRGB(a.color);
      if (a.size) c.size = a.size;
      if (a.baseline) c.baselineShift = a.baseline;
    }
  };
  S.image = function (path, x, y, w, h) {
    var p = doc.placedItems.add(); p.file = new File(path);
    p.width = w; p.height = h; p.left = X(x); p.top = Y(y); return p;
  };
  // Capture under the bezel, clipped to the screen's corners; the bezel itself untouched
  // (Apple: product images "as is" — no crop, tilt, shadow, nothing entering the screen).
  // Returns geometry; capY(pt) maps a point y in the capture (3× for iPhone) to the slide.
  S.device = function (capture, bezel, x, y, s, scale) {
    var sx = x + dev.sx * s, sy = y + dev.sy * s, sw = dev.sw * s, sh = dev.sh * s;
    var g = doc.groupItems.add();
    S.image(capture, sx, sy, sw, sh).move(g, ElementPlacement.PLACEATEND);
    var clip = doc.pathItems.roundedRectangle(Y(sy), X(sx), sw, sh, dev.r * s, dev.r * s);
    clip.move(g, ElementPlacement.PLACEATBEGINNING); clip.clipping = true; g.clipped = true;
    S.image(bezel, x, y, dev.bw * s, dev.bh * s);
    var px = scale || 3;
    return { x: x, y: y, s: s, w: dev.bw * s, h: dev.bh * s, capY: function (pt) { return y + (dev.sy + pt * px) * s; } };
  };
  // Largest device that fits below `top` (bottom margin, max width), centred unless o.x(s).
  S.fitDevice = function (capture, bezel, top, o) {
    o = o || {};
    var bottom = o.bottom || 70, maxW = o.maxW || (dev.W - 160);
    var s = Math.min((dev.H - bottom - top) / dev.bh, maxW / dev.bw);
    var x = (o.x !== undefined) ? o.x(s) : (dev.W - dev.bw * s) / 2;
    return S.device(capture, bezel, x, dev.H - bottom - dev.bh * s, s, o.scale);
  };
  // Tile a seamless SVG pattern over a region, clipped. Keep patterns off text and numbers.
  S.pattern = function (svgPath, tileW, tileH, x, y, w, h, scale, opacity) {
    var grp = doc.groupItems.add(), tw = tileW * scale / 100, th = tileH * scale / 100;
    var proto = doc.groupItems.createFromFile(new File(svgPath)); proto.resize(scale, scale);
    for (var ty = 0; ty * th < h + th; ty++) for (var tx = 0; tx * tw < w + tw; tx++) {
      var d = proto.duplicate(grp, ElementPlacement.PLACEATEND); d.left = X(x + tx * tw); d.top = Y(y + ty * th);
    }
    proto.remove();
    var clip = doc.pathItems.rectangle(Y(y), X(x), w, h);
    clip.move(grp, ElementPlacement.PLACEATBEGINNING); clip.clipping = true; grp.clipped = true;
    grp.opacity = opacity || 100; return grp;
  };
  return S;
}

// Save the .ai and export every artboard as PNG at 1× (exact store size) into outDir/1x/.
function shotlineExport(doc, outDir, aiName) {
  new Folder(outDir).create();
  doc.saveAs(new File(outDir + '/' + aiName));
  var opts = new ExportForScreensOptionsPNG24(); opts.scaleType = ExportForScreensScaleType.SCALEBYFACTOR; opts.scaleTypeValue = 1; opts.transparency = false;
  var it = new ExportForScreensItemToExport(); it.artboards = '1-' + doc.artboards.length; it.document = false;
  doc.exportForScreens(new Folder(outDir), ExportForScreensType.SE_PNG24, opts, it);
}

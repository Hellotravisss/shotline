// Minimal slide: headline + device. Set the three paths, then run:
//   osascript -e 'tell application id "com.adobe.illustrator" to do javascript file (POSIX file "/abs/path/example.jsx")'
// (Illustrator Beta: com.adobe.illustratorBeta). The fonts must be installed for Illustrator.
#target illustrator
#include "lib.jsx"
(function () {
  var CAPTURE = (typeof SHOTLINE_CAPTURE !== 'undefined') ? SHOTLINE_CAPTURE : '/abs/path/raw/en-iphone-home.png';
  var BEZEL = (typeof SHOTLINE_BEZEL !== 'undefined') ? SHOTLINE_BEZEL : '/abs/path/iPhone 17 Pro - Silver - Portrait.png';
  var OUT = (typeof SHOTLINE_OUT !== 'undefined') ? SHOTLINE_OUT : '/abs/path/out/example';
  app.userInteractionLevel = UserInteractionLevel.DONTDISPLAYALERTS;
  var dev = SHOTLINE_DEVICES.iphone;
  var doc = app.documents.add(DocumentColorSpace.RGB, dev.W, dev.H, 1);
  var S = Slides(doc, 0, dev);
  S.rect(0, 0, S.W, S.H, S.radial([[0, '#2B2E36'], [60, '#15171C'], [100, '#0B0C10']]));
  S.text('Your app,\rone idea per slide', S.W / 2, 220, 'Georgia-Bold', 110, '#FFFFFF', { align: 'center' });
  S.fitDevice(CAPTURE, BEZEL, 560);
  shotlineExport(doc, OUT, 'example.ai');
  doc.close(SaveOptions.DONOTSAVECHANGES);
  return 'ok';
})();

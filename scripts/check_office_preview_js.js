const assert = require('assert');
const path = require('path');

global.window = {};
global.layui = { use() {} };
global.$ = function jqueryStub() {
  return { find() { return { css() {} }; } };
};

require(path.join(__dirname, '..', 'static', 'js', 'office_preview.js'));

assert.ok(window.OfficePreviewUtils, 'OfficePreviewUtils should be exported');
assert.strictEqual(window.OfficePreviewUtils.getFileExtension('demo.Report.PDF'), '.pdf');
assert.strictEqual(window.OfficePreviewUtils.getFileExtension('no-extension'), '');
assert.strictEqual(window.OfficePreviewUtils.getMimeType('.mp3'), 'audio/mpeg');
assert.strictEqual(window.OfficePreviewUtils.getMimeType('.webm'), 'video/webm');
assert.strictEqual(window.OfficePreviewUtils.getMimeType('.unknown'), 'application/octet-stream');

assert.deepStrictEqual(
  window.OfficePreviewUtils.buildOfficePreviewData('demo.docx', '/media/demo.docx', '.docx'),
  {
    name: 'demo.docx',
    office_type: 'DOCX',
    file_path: '/media/demo.docx',
    preview_options: [{
      name: '文档内容',
      type: 'iframe',
      content: '/media/demo.docx',
    }],
  }
);

assert.strictEqual(window.OfficePreviewUtils.escapeHtml('<b>"x"</b>'), '&lt;b&gt;&quot;x&quot;&lt;/b&gt;');

console.log('office preview helper checks passed');

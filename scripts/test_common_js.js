const assert = require('assert');
const path = require('path');

const listeners = {};
global.window = {
  location: { href: '' },
};
global.window.top = global.window;
global.document = {
  cookie: 'csrftoken=cookie-token; other=value',
  addEventListener(name, handler) {
    listeners[name] = handler;
  },
  querySelector(selector) {
    if (selector === '[name=csrfmiddlewaretoken]') {
      return { value: 'input-token' };
    }
    return null;
  },
};
global.alert = function alert() {};

const common = require(path.join(__dirname, '..', 'static', 'js', 'common.js'));

assert.strictEqual(common.getCookie('csrftoken'), 'cookie-token');
assert.strictEqual(common.getCookie('other'), 'value');
assert.strictEqual(common.getCookie('missing'), '');
assert.strictEqual(
  common.escapeHtml('<span title="x">Tom & Jerry</span>'),
  '&lt;span title=&quot;x&quot;&gt;Tom &amp; Jerry&lt;/span&gt;'
);
assert.strictEqual(common.escapeAttr('`quoted`'), '&#96;quoted&#96;');
assert.strictEqual(common.getCsrfToken(), 'input-token');

global.document.querySelector = () => null;
assert.strictEqual(common.getCsrfToken(), 'cookie-token');

let openedOptions = null;
const fakeLayer = {
  open(options) {
    openedOptions = options;
    if (options.success) {
      options.success({ css(styles) { this.styles = styles; } }, 1);
    }
    return 7;
  },
};

assert.strictEqual(
  common.openRightPopup(fakeLayer, '编辑', '/edit/1/', { width: '70%', onClose: () => {} }),
  7
);
assert.strictEqual(openedOptions.type, 2);
assert.strictEqual(openedOptions.offset, 'r');
assert.deepStrictEqual(openedOptions.area, ['70%', '100%']);

console.log('common.js helper tests passed');

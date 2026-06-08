const { getDefaultConfig } = require('expo/metro-config');
const { withUniwindConfig } = require('uniwind/metro');
const fs = require('fs');
const path = require('path');

let config = getDefaultConfig(__dirname);

// Enable browser caching with revalidation for faster iframe reloads
// Metro defaults to no-store which forces full re-download every time
config.server = {
  ...config.server,
  enhanceMiddleware: (middleware) => {
    return (req, res, next) => {
      // Intercept writeHead to modify cache headers before they're sent
      const originalWriteHead = res.writeHead.bind(res);
      res.writeHead = function(statusCode, statusMessage, headers) {
        // Handle different argument patterns
        let hdrs = headers;
        if (typeof statusMessage === 'object') {
          hdrs = statusMessage;
          statusMessage = undefined;
        }

        // Modify Cache-Control header if present
        if (hdrs && hdrs['Cache-Control']) {
          hdrs['Cache-Control'] = hdrs['Cache-Control'].replace('no-store, ', '');
        }

        // Also check res._headers (internal node.js headers)
        if (res.getHeader && res.getHeader('Cache-Control')) {
          const cc = res.getHeader('Cache-Control');
          if (typeof cc === 'string' && cc.includes('no-store')) {
            res.setHeader('Cache-Control', cc.replace('no-store, ', ''));
          }
        }

        if (statusMessage) {
          return originalWriteHead(statusCode, statusMessage, hdrs);
        } else if (hdrs) {
          return originalWriteHead(statusCode, hdrs);
        } else {
          return originalWriteHead(statusCode);
        }
      };
      return middleware(req, res, next);
    };
  },
};

// DO NOT MODIFY - Dynamic Cayu tagger loading for browser automation
// The tagger files are injected by cayu-pilot in dev instances only
const cayuResolverPath = path.resolve(__dirname, './lib/cayu/metro-resolver.js');
if (fs.existsSync(cayuResolverPath)) {
  try {
    const { withCayuTagger } = require('./lib/cayu/metro-resolver');
    config = withCayuTagger(config);
  } catch (e) {
    console.warn('[Cayu] Failed to load tagger:', e.message);
  }
}

// Uniwind MUST be the outermost wrapper
module.exports = withUniwindConfig(config, {
  // Path to global CSS file
  cssEntryFile: './global.css',
  // TypeScript definitions for Tailwind classes
  dtsFile: './uniwind-types.d.ts',
});

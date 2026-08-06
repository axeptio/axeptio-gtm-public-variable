___TERMS_OF_SERVICE___

By creating or modifying this file you agree to Google Tag Manager's Community
Template Gallery Developer Terms of Service available at
https://developers.google.com/tag-manager/gallery-tos (or such other URL as
Google may provide), as modified from time to time.


___INFO___

{
  "type": "MACRO",
  "id": "cvt_temp_public_id",
  "version": 1,
  "securityGroups": [],
  "displayName": "Axeptio Consent State",
  "categories": [
    "TAG_MANAGEMENT",
    "PERSONALIZATION"
  ],
  "description": "Reads an Axeptio consent signal — the vendors the visitor authorized, the Google Consent Mode state, or a GPP field — from the dataLayer, falling back to the Axeptio cookies so it still resolves on a repeat visit before the widget has loaded.",
  "containerContexts": [
    "WEB"
  ]
}


___TEMPLATE_PARAMETERS___

[
  {
    "type": "SELECT",
    "name": "signal",
    "displayName": "Consent signal",
    "macrosInSelect": false,
    "selectItems": [
      {
        "value": "axeptio_authorized_vendors",
        "displayValue": "Authorized vendors (array of vendor names)"
      },
      {
        "value": "consent_mode",
        "displayValue": "Google Consent Mode state (object)"
      },
      {
        "value": "gpp_string",
        "displayValue": "GPP string"
      },
      {
        "value": "mspa_mode",
        "displayValue": "MSPA mode"
      },
      {
        "value": "gpc_active",
        "displayValue": "GPC active (boolean)"
      },
      {
        "value": "consent_type",
        "displayValue": "GPP consent type (opt-in / opt-out)"
      }
    ],
    "simpleValueType": true,
    "defaultValue": "axeptio_authorized_vendors",
    "help": "Which Axeptio consent signal this variable returns. <b>Authorized vendors</b> and <b>Google Consent Mode state</b> are published with the <code>axeptio_update</code> event (Consent Mode only when the project has Google Consent Mode enabled). The <b>GPP</b> signals are published with the <code>gpp_consent_given</code>, <code>gpp_consent_refused</code> and <code>gpp_consent_updated</code> events on GPP-enabled projects."
  },
  {
    "type": "SELECT",
    "name": "source",
    "displayName": "Read from",
    "macrosInSelect": false,
    "selectItems": [
      {
        "value": "auto",
        "displayValue": "Data layer, falling back to the Axeptio cookies"
      },
      {
        "value": "datalayer",
        "displayValue": "Data layer only"
      },
      {
        "value": "cookie",
        "displayValue": "Axeptio cookies only"
      }
    ],
    "simpleValueType": true,
    "defaultValue": "auto",
    "help": "The data layer only carries a signal once the Axeptio widget has pushed it, which on a repeat visit can be later than the tags you want to gate — the consent cookies are already there when the page starts parsing. <b>Data layer, falling back to the Axeptio cookies</b> reads the data layer first and only reads a cookie when that key has not been pushed yet.<br><br>Two limits apply to the cookie fallback: <b>GPC active</b> and <b>GPP consent type</b> are computed by the widget from its project configuration and are never stored, so they resolve from the data layer only; and a consent cookie compressed by the widget's <code>compressUserCookie</code> setting cannot be decoded here, so <b>Google Consent Mode state</b> and <b>MSPA mode</b> then fall back to nothing rather than to a wrong value."
  },
  {
    "type": "GROUP",
    "name": "cookieNamesGroup",
    "displayName": "Cookie names (advanced)",
    "groupStyle": "ZIPPY_CLOSED",
    "enablingConditions": [
      {
        "paramName": "source",
        "paramValue": "datalayer",
        "type": "NOT_EQUALS"
      }
    ],
    "subParams": [
      {
        "type": "TEXT",
        "name": "jsonCookieName",
        "displayName": "Consent JSON cookie",
        "simpleValueType": true,
        "defaultValue": "axeptio_cookies",
        "help": "Only change this if the site overrides <code>jsonCookieName</code> in <code>window.axeptioSettings</code>. A renamed cookie must also be added to this template's cookie permission in your container, otherwise reading it is blocked."
      },
      {
        "type": "TEXT",
        "name": "authorizedVendorsCookieName",
        "displayName": "Authorized vendors cookie",
        "simpleValueType": true,
        "defaultValue": "axeptio_authorized_vendors",
        "help": "Only change this if the site overrides <code>authorizedVendorsCookieName</code> in <code>window.axeptioSettings</code>. A renamed cookie must also be added to this template's cookie permission in your container."
      },
      {
        "type": "TEXT",
        "name": "gppCookieName",
        "displayName": "GPP string cookie",
        "simpleValueType": true,
        "defaultValue": "axeptio_gpp_string",
        "help": "Only change this if the site overrides <code>gppCookieName</code> in <code>window.axeptioSettings</code>. A renamed cookie must also be added to this template's cookie permission in your container."
      }
    ]
  }
]


___SANDBOXED_JS_FOR_WEB_TEMPLATE___

const copyFromDataLayer = require('copyFromDataLayer');
const getCookieValues = require('getCookieValues');
const decodeUriComponent = require('decodeUriComponent');
const getType = require('getType');
const JSON = require('JSON');

// The widget compresses the consent JSON cookie with lz-string once it grows past
// the compressUserCookie threshold, and marks it with this prefix. There is no
// lz-string in the sandbox, so a marked value is unreadable here — return nothing
// rather than a garbled parse. Mirrors COOKIE_COMPRESSION_MARKER in widget-client.
const COMPRESSION_MARKER = 'lzc1.';

// The widget's own bookkeeping keys inside the consent JSON cookie carry this
// prefix. It is configurable (settings.metadataPrefix) but effectively never
// changed; the Axeptio CMP tag template hardcodes it the same way.
const METADATA_PREFIX = '$$';

// Backward compatibility: instances saved before these parameters existed
// deserialise with data.signal / data.source === undefined. Falling back keeps
// already-published containers working across this update, and hands them the
// cookie fallback, which is the whole point of it.
const signal = data.signal || 'axeptio_authorized_vendors';
const source = data.source || 'auto';

const firstCookie = (name) => {
  const values = getCookieValues(name);
  return (values && values.length > 0) ? values[0] : undefined;
};

// The consent JSON cookie as an object. Whether the value arrives percent-encoded
// depends on who wrote it, so retry through decodeUriComponent — the same two-step
// the Axeptio CMP tag template uses. Sandboxed JSON.parse returns undefined on a
// parse failure instead of throwing, which is what makes the retry readable.
const readChoices = () => {
  const raw = firstCookie(data.jsonCookieName || 'axeptio_cookies');
  if (!raw || raw.indexOf(COMPRESSION_MARKER) === 0) {
    return undefined;
  }
  let choices = JSON.parse(raw);
  if (choices === undefined) {
    const decoded = decodeUriComponent(raw);
    choices = (decoded !== undefined) ? JSON.parse(decoded) : undefined;
  }
  return getType(choices) === 'object' ? choices : undefined;
};

const fromCookies = () => {
  if (signal === 'axeptio_authorized_vendors') {
    // Stored comma-separated *and* comma-enclosed: ",google_analytics,facebook_pixel,".
    // Dropping the empty segments yields the same array type the dataLayer carries,
    // so a tag never has to care which source answered.
    const raw = firstCookie(data.authorizedVendorsCookieName || 'axeptio_authorized_vendors');
    if (!raw) {
      return undefined;
    }
    const vendors = [];
    raw.split(',').forEach((vendor) => {
      if (vendor) {
        vendors.push(vendor);
      }
    });
    return vendors;
  }

  if (signal === 'gpp_string') {
    return firstCookie(data.gppCookieName || 'axeptio_gpp_string');
  }

  if (signal === 'consent_mode' || signal === 'mspa_mode') {
    const choices = readChoices();
    if (!choices) {
      return undefined;
    }
    if (signal === 'mspa_mode') {
      return choices[METADATA_PREFIX + 'mspaMode'];
    }
    // Only a completed journey carries a consent state worth acting on — the same
    // gate the widget applies before replaying its stored state to gtag.
    if (!choices[METADATA_PREFIX + 'completed']) {
      return undefined;
    }
    const consentMode = choices[METADATA_PREFIX + 'googleConsentMode'];
    return getType(consentMode) === 'object' ? consentMode : undefined;
  }

  // gpc_active and consent_type are derived by the widget from the project
  // configuration it fetches, and are never persisted. No cookie can answer them.
  return undefined;
};

if (source === 'cookie') {
  return fromCookies();
}

// dataLayer version 1 is deliberate — do not "fix" it to the recommended 2.
// Version 2 resolves against Tag Manager's merged data layer model. The Axeptio
// widget pushes a *shrinking* authorized-vendor array when a visitor withdraws
// consent, and the merged model can retain stale trailing entries from the
// previous, longer push. Version 1 returns the raw last-pushed value, which is
// the only correct reading of a consent signal.
const fromDataLayer = copyFromDataLayer(signal, 1);

if (source === 'datalayer') {
  return fromDataLayer;
}

// Strictly undefined, never merely falsy: gpc_active === false and gpp_string === ''
// are real answers, and must not be thrown away in favour of a staler cookie.
return fromDataLayer === undefined ? fromCookies() : fromDataLayer;


___WEB_PERMISSIONS___

[
  {
    "instance": {
      "key": {
        "publicId": "read_data_layer",
        "versionId": "1"
      },
      "param": [
        {
          "key": "allowedKeys",
          "value": {
            "type": 1,
            "string": "specific"
          }
        },
        {
          "key": "keyPatterns",
          "value": {
            "type": 2,
            "listItem": [
              {
                "type": 1,
                "string": "axeptio_authorized_vendors"
              },
              {
                "type": 1,
                "string": "consent_mode"
              },
              {
                "type": 1,
                "string": "gpp_string"
              },
              {
                "type": 1,
                "string": "mspa_mode"
              },
              {
                "type": 1,
                "string": "gpc_active"
              },
              {
                "type": 1,
                "string": "consent_type"
              }
            ]
          }
        }
      ]
    },
    "clientAnnotations": {
      "isEditedByUser": true
    },
    "isRequired": true
  },
  {
    "instance": {
      "key": {
        "publicId": "get_cookies",
        "versionId": "1"
      },
      "param": [
        {
          "key": "cookieAccess",
          "value": {
            "type": 1,
            "string": "specific"
          }
        },
        {
          "key": "cookieNames",
          "value": {
            "type": 2,
            "listItem": [
              {
                "type": 1,
                "string": "axeptio_cookies"
              },
              {
                "type": 1,
                "string": "axeptio_authorized_vendors"
              },
              {
                "type": 1,
                "string": "axeptio_gpp_string"
              }
            ]
          }
        }
      ]
    },
    "clientAnnotations": {
      "isEditedByUser": true
    },
    "isRequired": true
  }
]


___TESTS___

scenarios:
- name: A legacy instance saved before the signal parameter returns authorized vendors
  code: |-
    const mockData = {};
    let requestedKey;

    mock('copyFromDataLayer', (key, version) => {
      requestedKey = key;
      return ['google_analytics', 'facebook_pixel'];
    });

    const variableResult = runCode(mockData);

    assertThat(requestedKey).isEqualTo('axeptio_authorized_vendors');
    assertThat(variableResult).isEqualTo(['google_analytics', 'facebook_pixel']);
- name: Authorized vendors selected explicitly
  code: |-
    const mockData = {signal: 'axeptio_authorized_vendors'};
    let requestedKey;

    mock('copyFromDataLayer', (key, version) => {
      requestedKey = key;
      return ['google_analytics'];
    });

    const variableResult = runCode(mockData);

    assertThat(requestedKey).isEqualTo('axeptio_authorized_vendors');
    assertThat(variableResult).isEqualTo(['google_analytics']);
- name: Google Consent Mode state is returned as an object
  code: |-
    const consentMode = {
      analytics_storage: 'granted',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied'
    };
    const mockData = {signal: 'consent_mode'};
    let requestedKey;

    mock('copyFromDataLayer', (key, version) => {
      requestedKey = key;
      return consentMode;
    });

    const variableResult = runCode(mockData);

    assertThat(requestedKey).isEqualTo('consent_mode');
    assertThat(variableResult).isEqualTo(consentMode);
- name: GPP string is returned verbatim
  code: |-
    const mockData = {signal: 'gpp_string'};
    let requestedKey;

    mock('copyFromDataLayer', (key, version) => {
      requestedKey = key;
      return 'DBABL~BVQVAAAAAg.QA';
    });

    const variableResult = runCode(mockData);

    assertThat(requestedKey).isEqualTo('gpp_string');
    assertThat(variableResult).isEqualTo('DBABL~BVQVAAAAAg.QA');
- name: A falsy GPP signal is returned as-is and not replaced by a default
  code: |-
    const mockData = {signal: 'gpc_active'};
    let requestedKey;

    mock('copyFromDataLayer', (key, version) => {
      requestedKey = key;
      return false;
    });

    const variableResult = runCode(mockData);

    assertThat(requestedKey).isEqualTo('gpc_active');
    assertThat(variableResult).isEqualTo(false);
- name: An absent key with no cookie resolves to undefined
  code: |-
    const mockData = {signal: 'axeptio_authorized_vendors'};

    mock('copyFromDataLayer', (key, version) => {
      return undefined;
    });
    mock('getCookieValues', (name) => {
      return [];
    });

    const variableResult = runCode(mockData);

    assertThat(variableResult).isUndefined();
- name: The dataLayer is always read with version 1
  code: |-
    const mockData = {signal: 'consent_mode'};
    let requestedVersion;

    mock('copyFromDataLayer', (key, version) => {
      requestedVersion = version;
      return {};
    });

    runCode(mockData);

    assertThat(requestedVersion).isEqualTo(1);
- name: A legacy instance falls back to the cookie
  code: |-
    // The load-bearing half of the backward-compatibility story: an instance
    // saved before the source parameter existed has data.source === undefined
    // and must resolve to the fallback, since nobody re-opens their variable
    // after a gallery update. Without this the legacy default could be changed
    // to datalayer and every other scenario would still pass.
    const mockData = {};
    let requestedCookie;

    mock('copyFromDataLayer', (key, version) => {
      return undefined;
    });
    mock('getCookieValues', (name) => {
      requestedCookie = name;
      return [',google_analytics,'];
    });

    const variableResult = runCode(mockData);

    assertThat(requestedCookie).isEqualTo('axeptio_authorized_vendors');
    assertThat(variableResult).isEqualTo(['google_analytics']);
- name: The cookie is left alone while the dataLayer still answers
  code: |-
    const mockData = {signal: 'axeptio_authorized_vendors', source: 'auto'};
    let cookieWasRead = false;

    mock('copyFromDataLayer', (key, version) => {
      return ['google_analytics'];
    });
    mock('getCookieValues', (name) => {
      cookieWasRead = true;
      return [',stale_vendor,'];
    });

    const variableResult = runCode(mockData);

    assertThat(cookieWasRead).isEqualTo(false);
    assertThat(variableResult).isEqualTo(['google_analytics']);
- name: Authorized vendors fall back to the comma-enclosed cookie as an array
  code: |-
    const mockData = {signal: 'axeptio_authorized_vendors', source: 'auto'};
    let requestedCookie;

    mock('copyFromDataLayer', (key, version) => {
      return undefined;
    });
    mock('getCookieValues', (name) => {
      requestedCookie = name;
      return [',google_analytics,facebook_pixel,'];
    });

    const variableResult = runCode(mockData);

    assertThat(requestedCookie).isEqualTo('axeptio_authorized_vendors');
    assertThat(variableResult).isEqualTo(['google_analytics', 'facebook_pixel']);
- name: Google Consent Mode state falls back to the consent JSON cookie
  code: |-
    const mockData = {signal: 'consent_mode', source: 'cookie'};

    mock('getCookieValues', (name) => {
      return ['{"google_analytics":true,"$$completed":true,"$$googleConsentMode":{"analytics_storage":"granted","ad_storage":"denied","ad_user_data":"denied","ad_personalization":"denied","version":2}}'];
    });

    const variableResult = runCode(mockData);

    assertThat(variableResult).isEqualTo({
      analytics_storage: 'granted',
      ad_storage: 'denied',
      ad_user_data: 'denied',
      ad_personalization: 'denied',
      version: 2
    });
- name: An unfinished consent journey yields no Consent Mode state
  code: |-
    const mockData = {signal: 'consent_mode', source: 'cookie'};

    mock('getCookieValues', (name) => {
      return ['{"$$completed":false,"$$googleConsentMode":{"ad_storage":"granted"}}'];
    });

    const variableResult = runCode(mockData);

    assertThat(variableResult).isUndefined();
- name: A compressed consent cookie is skipped rather than mis-parsed
  code: |-
    const mockData = {signal: 'consent_mode', source: 'cookie'};

    mock('getCookieValues', (name) => {
      return ['lzc1.EYFwpgTghgtgLmAJgSwHYHMD2A'];
    });
    mock('decodeUriComponent', (value) => {
      return value;
    });

    const variableResult = runCode(mockData);

    assertThat(variableResult).isUndefined();
    // The marker must short-circuit before the decode retry. Asserting only on
    // the undefined result proves nothing: an lzc1. value fails JSON.parse
    // anyway, so the generic parse-failure path returns undefined too.
    assertApi('decodeUriComponent').wasNotCalled();
- name: A percent-encoded consent cookie is decoded before parsing
  code: |-
    const mockData = {signal: 'mspa_mode', source: 'cookie'};

    mock('getCookieValues', (name) => {
      return ['%7B%22%24%24completed%22%3Atrue%2C%22%24%24mspaMode%22%3A%22opt-out%22%7D'];
    });

    const variableResult = runCode(mockData);

    assertThat(variableResult).isEqualTo('opt-out');
- name: The GPP string falls back to its own cookie
  code: |-
    const mockData = {signal: 'gpp_string', source: 'auto'};
    let requestedCookie;

    mock('copyFromDataLayer', (key, version) => {
      return undefined;
    });
    mock('getCookieValues', (name) => {
      requestedCookie = name;
      return ['DBABL~BVQVAAAAAg.QA'];
    });

    const variableResult = runCode(mockData);

    assertThat(requestedCookie).isEqualTo('axeptio_gpp_string');
    assertThat(variableResult).isEqualTo('DBABL~BVQVAAAAAg.QA');
- name: GPC active has no cookie to fall back to
  code: |-
    const mockData = {signal: 'gpc_active', source: 'auto'};
    let cookieWasRead = false;

    mock('copyFromDataLayer', (key, version) => {
      return undefined;
    });
    mock('getCookieValues', (name) => {
      cookieWasRead = true;
      return ['{"$$completed":true}'];
    });

    const variableResult = runCode(mockData);

    assertThat(cookieWasRead).isEqualTo(false);
    assertThat(variableResult).isUndefined();
- name: An empty dataLayer value is kept instead of falling back
  code: |-
    const mockData = {signal: 'gpp_string', source: 'auto'};
    let cookieWasRead = false;

    mock('copyFromDataLayer', (key, version) => {
      return '';
    });
    mock('getCookieValues', (name) => {
      cookieWasRead = true;
      return ['DBABL~stale'];
    });

    const variableResult = runCode(mockData);

    assertThat(cookieWasRead).isEqualTo(false);
    assertThat(variableResult).isEqualTo('');
- name: Data layer only never touches the cookies
  code: |-
    const mockData = {signal: 'axeptio_authorized_vendors', source: 'datalayer'};
    let cookieWasRead = false;

    mock('copyFromDataLayer', (key, version) => {
      return undefined;
    });
    mock('getCookieValues', (name) => {
      cookieWasRead = true;
      return [',google_analytics,'];
    });

    const variableResult = runCode(mockData);

    assertThat(cookieWasRead).isEqualTo(false);
    assertThat(variableResult).isUndefined();
- name: A renamed consent cookie is honoured
  code: |-
    const mockData = {
      signal: 'consent_mode',
      source: 'cookie',
      jsonCookieName: 'custom_consent'
    };
    let requestedCookie;

    mock('getCookieValues', (name) => {
      requestedCookie = name;
      return ['{"$$completed":true,"$$googleConsentMode":{"ad_storage":"granted"}}'];
    });

    const variableResult = runCode(mockData);

    assertThat(requestedCookie).isEqualTo('custom_consent');
    assertThat(variableResult).isEqualTo({ad_storage: 'granted'});


___NOTES___

Created on 08/01/2021 à 14:29:41
Updated to expose the Google Consent Mode and GPP signals published by the
Axeptio widget, alongside the authorized-vendor list, and to fall back to the
Axeptio consent cookies when the matching dataLayer key has not been pushed yet.

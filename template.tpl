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
  "description": "Reads an Axeptio consent signal from the dataLayer: the list of vendors the visitor authorized, the Google Consent Mode state, or a GPP field.",
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
    "help": "Which Axeptio dataLayer signal this variable returns. <b>Authorized vendors</b> and <b>Google Consent Mode state</b> are published with the <code>axeptio_update</code> event (Consent Mode only when the project has Google Consent Mode enabled). The <b>GPP</b> signals are published with the <code>gpp_consent_given</code>, <code>gpp_consent_refused</code> and <code>gpp_consent_updated</code> events on GPP-enabled projects. The variable is undefined until the matching event has been pushed."
  }
]


___SANDBOXED_JS_FOR_WEB_TEMPLATE___

const copyFromDataLayer = require('copyFromDataLayer');

// Backward compatibility: variable instances saved before the "signal" parameter
// existed deserialise with data.signal === undefined. Fall back to the original
// behaviour so already-published containers keep working across this update.
const key = data.signal || 'axeptio_authorized_vendors';

// dataLayer version 1 is deliberate — do not "fix" it to the recommended 2.
// Version 2 resolves against Tag Manager's merged data layer model. The Axeptio
// widget pushes a *shrinking* authorized-vendor array when a visitor withdraws
// consent, and the merged model can retain stale trailing entries from the
// previous, longer push. Version 1 returns the raw last-pushed value, which is
// the only correct reading of a consent signal.
return copyFromDataLayer(key, 1);


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
- name: An absent key resolves to undefined
  code: |-
    const mockData = {signal: 'axeptio_authorized_vendors'};

    mock('copyFromDataLayer', (key, version) => {
      return undefined;
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


___NOTES___

Created on 08/01/2021 à 14:29:41
Updated to expose the Google Consent Mode and GPP signals published by the
Axeptio widget, alongside the authorized-vendor list.

/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// Bump when cached documents may no longer share history with the server copy.
// v2: the server used to regenerate documents from HTML after API edits, so caches
// written before that was fixed could resurrect stale content on merge.
const DOCUMENT_CACHE_VERSION = "v2";

/**
 * @description IndexedDB database name holding the locally cached Yjs document
 * @param {string} docId
 * @returns {string}
 */
export const getDocumentCacheName = (docId: string): string => `plane-doc:${DOCUMENT_CACHE_VERSION}:${docId}`;

/**
 * @description best-effort removal of the cache written before versioned names existed
 * @param {string} docId
 */
export const deleteLegacyDocumentCache = (docId: string): void => {
  try {
    window.indexedDB?.deleteDatabase(docId);
  } catch {
    // ignore: cache cleanup is best effort
  }
};

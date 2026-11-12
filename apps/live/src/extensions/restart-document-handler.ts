/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// hocuspocus
import type { Document, Extension, Hocuspocus, onConfigurePayload } from "@hocuspocus/server";
import { mergeDocumentEditorHTMLIntoYDoc } from "@plane/editor";
import { logger } from "@plane/logger";
import { Redis } from "@/extensions/redis";
import { AdminCommand, isRestartDocumentCommand } from "@/types/admin-commands";
import type { ClientDocumentUpdateMessage, RestartDocumentCommandData } from "@/types/admin-commands";

/**
 * Extension to handle restart_document admin commands via the Redis admin channel.
 * Sent when a document's content is updated outside the collaborative session
 * (e.g. via the REST API). The new HTML is merged into the in-memory document as
 * an incremental Yjs update, so connected clients receive it live and the next
 * save keeps it. If the merge is not possible, clients are asked to reload.
 */
export class RestartDocumentHandler implements Extension {
  name = "RestartDocumentHandler";
  priority = 998;

  async onConfigure({ instance }: onConfigurePayload) {
    const redisExt = instance.configuration.extensions.find((ext) => ext instanceof Redis);

    if (!redisExt) {
      logger.warn("[RESTART_DOCUMENT_HANDLER] Redis extension not found");
      return;
    }

    redisExt.onAdminCommand<RestartDocumentCommandData>(AdminCommand.RESTART_DOCUMENT, async (data) => {
      if (!isRestartDocumentCommand(data)) {
        logger.error("[RESTART_DOCUMENT_HANDLER] Received invalid restart document command");
        return;
      }

      const { docId, descriptionHtml } = data;
      const document = instance.documents.get(docId);

      if (!document) {
        // Document not loaded in memory - the next load merges the outdated HTML
        return;
      }

      if (descriptionHtml != null && (await mergeIntoLoadedDocument(instance, document, descriptionHtml))) {
        return;
      }

      const updateMessage: ClientDocumentUpdateMessage = {
        type: "external_update",
        docId,
        timestamp: new Date().toISOString(),
      };

      let notified = 0;
      document.connections.forEach(({ connection }) => {
        try {
          connection.sendStateless(JSON.stringify(updateMessage));
          notified++;
        } catch (error) {
          logger.error("[RESTART_DOCUMENT_HANDLER] Failed to notify client:", error);
        }
      });

      logger.info(`[RESTART_DOCUMENT_HANDLER] Notified ${notified} client(s) of external update for ${docId}`);
    });

    logger.info("[RESTART_DOCUMENT_HANDLER] Registered with Redis extension");
  }
}

/**
 * Merge new HTML into a loaded document through a direct connection that reuses an
 * existing client's context, so the store hook can persist the result.
 * @returns whether the merge was applied
 */
const mergeIntoLoadedDocument = async (
  instance: Hocuspocus,
  document: Document,
  descriptionHtml: string
): Promise<boolean> => {
  const firstConnection = document.connections.values().next().value?.connection;
  if (!firstConnection) return false;

  try {
    const directConnection = await instance.openDirectConnection(document.name, firstConnection.context);
    try {
      if (!directConnection.document) return false;
      mergeDocumentEditorHTMLIntoYDoc(directConnection.document, descriptionHtml);
    } finally {
      // disconnecting persists the merged document through the store hook
      await directConnection.disconnect();
    }
    logger.info(`[RESTART_DOCUMENT_HANDLER] Merged external update into ${document.name}`);
    return true;
  } catch (error) {
    logger.error("[RESTART_DOCUMENT_HANDLER] Failed to merge external update:", error);
    return false;
  }
};

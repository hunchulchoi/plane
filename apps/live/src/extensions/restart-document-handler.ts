/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// hocuspocus
import type { Extension, onConfigurePayload } from "@hocuspocus/server";
import { logger } from "@plane/logger";
import { Redis } from "@/extensions/redis";
import { AdminCommand, isRestartDocumentCommand } from "@/types/admin-commands";
import type { ClientDocumentUpdateMessage, RestartDocumentCommandData } from "@/types/admin-commands";

/**
 * Extension to handle restart_document admin commands via the Redis admin channel.
 * Sent when a document's content is updated outside the collaborative session
 * (e.g. via the REST API): connected clients are notified so they can reload
 * the fresh document instead of overwriting it with their stale state.
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

      const { docId } = data;
      const document = instance.documents.get(docId);

      if (!document) {
        // Document not loaded in memory - no clients to notify
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

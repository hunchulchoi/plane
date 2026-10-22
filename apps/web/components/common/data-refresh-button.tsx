/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useRef, useState } from "react";
import { RefreshCw } from "lucide-react";
import { Button } from "@makeplane/propel/components/button";
import { setToast } from "@plane/blocks/toast";
import { useTranslation } from "@plane/i18n";

type Props = {
  onRefresh: () => Promise<unknown>;
  disabled?: boolean;
};

/** Shows the completion time of the last successful manual refresh in this view. */
export function DataRefreshButton({ onRefresh, disabled = false }: Props) {
  const { t } = useTranslation();
  const inFlight = useRef(false);
  const [refreshing, setRefreshing] = useState(false);
  const [lastRefreshed, setLastRefreshed] = useState<Date | null>(null);

  const refresh = async () => {
    if (disabled || inFlight.current) return;
    inFlight.current = true;
    setRefreshing(true);
    try {
      await onRefresh();
      setLastRefreshed(new Date());
    } catch {
      setToast({ type: "error", title: t("data_refresh.error") });
    } finally {
      inFlight.current = false;
      setRefreshing(false);
    }
  };

  return (
    <div className="flex shrink-0 flex-col items-end gap-0.5 sm:flex-row sm:items-center sm:gap-2">
      <span className="text-11 whitespace-nowrap text-tertiary" role="status" aria-live="polite">
        <span className="sr-only lg:not-sr-only">{t("data_refresh.last_refreshed")}: </span>
        {lastRefreshed ? (
          <time dateTime={lastRefreshed.toISOString()} title={lastRefreshed.toLocaleString()}>
            {lastRefreshed.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" })}
          </time>
        ) : (
          <>
            <span className="hidden sm:inline">{t("data_refresh.not_refreshed")}</span>
            <span className="sm:hidden" aria-hidden="true">
              —
            </span>
            <span className="sr-only sm:hidden">{t("data_refresh.not_refreshed")}</span>
          </>
        )}
      </span>
      <Button
        variant="secondary"
        size="sm"
        stretch="auto"
        icon={<RefreshCw className="size-3.5" aria-hidden="true" />}
        label={refreshing ? t("refreshing") : t("refresh")}
        loading={refreshing}
        disabled={disabled}
        onClick={() => void refresh()}
      />
    </div>
  );
}

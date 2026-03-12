import { useCallback, useState } from 'react';

import {
  fetchActivityTimeline,
  type ActivityTimelineItemRecord,
} from '../../lib/backend/activity';
import type { RunAsyncAction } from './shared';

export function useActivityController({
  runAsyncAction,
}: {
  runAsyncAction: RunAsyncAction;
}) {
  const [activityItems, setActivityItems] = useState<ActivityTimelineItemRecord[]>([]);
  const [isLoadingActivity, setIsLoadingActivity] = useState(false);

  const loadActivity = useCallback(async () => {
    const response = await runAsyncAction(() => fetchActivityTimeline(), {
      setPending: setIsLoadingActivity,
      errorMessage: 'Failed to load activity timeline.',
    });
    if (!response) {
      return null;
    }

    setActivityItems(response.items);
    return response;
  }, [runAsyncAction]);

  return {
    activityItems,
    isLoadingActivity,
    loadActivity,
  };
}

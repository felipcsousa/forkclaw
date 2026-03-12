import type { useAppController } from '../hooks/useAppController';
import { ActivityTimelinePanel } from '../components/ActivityTimelinePanel';

type AppController = ReturnType<typeof useAppController>;

export interface ActivityViewProps {
  activity: AppController['activity'];
  onOpenSubagent: AppController['chat']['handleOpenSubagent'];
}

export function ActivityView({
  activity,
  onOpenSubagent,
}: ActivityViewProps) {
  return (
    <ActivityTimelinePanel
      items={activity.activityItems}
      isLoading={activity.isLoadingActivity}
      onOpenSubagent={onOpenSubagent}
    />
  );
}

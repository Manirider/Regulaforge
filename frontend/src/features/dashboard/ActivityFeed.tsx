import { Clock, Shield, ClipboardCheck, FileText, Users } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { cn, formatRelativeTime } from "@/lib/utils";

interface Activity {
  id: string;
  type: string;
  description: string;
  user_name: string;
  timestamp: string;
}

interface ActivityFeedProps {
  activities: Activity[];
  className?: string;
}

const activityIcons: Record<string, React.ReactNode> = {
  regulation: <Shield className="h-4 w-4" />,
  assessment: <ClipboardCheck className="h-4 w-4" />,
  document: <FileText className="h-4 w-4" />,
  user: <Users className="h-4 w-4" />,
};

const activityColors: Record<string, string> = {
  regulation: "bg-indigo-100 text-indigo-600 dark:bg-indigo-950/30 dark:text-indigo-400",
  assessment: "bg-emerald-100 text-emerald-600 dark:bg-emerald-950/30 dark:text-emerald-400",
  document: "bg-blue-100 text-blue-600 dark:bg-blue-950/30 dark:text-blue-400",
  user: "bg-purple-100 text-purple-600 dark:bg-purple-950/30 dark:text-purple-400",
};

export function ActivityFeed({ activities, className }: ActivityFeedProps) {
  return (
    <Card className={className}>
      <CardHeader>
        <CardTitle>Recent Activity</CardTitle>
      </CardHeader>
      <div className="space-y-0">
        {activities.length === 0 ? (
          <p className="py-8 text-center text-sm text-surface-500">
            No recent activity
          </p>
        ) : (
          activities.slice(0, 10).map((activity) => (
            <div
              key={activity.id}
              className="flex items-start gap-3 border-b border-surface-100 py-3 last:border-0 dark:border-surface-700"
            >
              <div
                className={cn(
                  "flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-lg",
                  activityColors[activity.type] || "bg-surface-100 text-surface-600 dark:bg-surface-700 dark:text-surface-400",
                )}
              >
                {activityIcons[activity.type] || <Clock className="h-4 w-4" />}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm text-surface-900 dark:text-surface-100">
                  {activity.description}
                </p>
                <p className="text-xs text-surface-500 dark:text-surface-400">
                  {activity.user_name} &middot;{" "}
                  {formatRelativeTime(activity.timestamp)}
                </p>
              </div>
            </div>
          ))
        )}
      </div>
    </Card>
  );
}

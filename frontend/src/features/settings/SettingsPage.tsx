import { useState } from "react";
import { Moon, Sun, Save } from "lucide-react";
import { Card, CardHeader, CardTitle } from "@/components/ui/Card";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { useTheme } from "@/hooks/useTheme";
import { useChangePassword } from "@/hooks/useAuth";
import { getErrorMessage } from "@/lib/api-client";
import toast from "react-hot-toast";

export function SettingsPage() {
  const { isDark, toggle } = useTheme();
  const changePassword = useChangePassword();
  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");

  function handleChangePassword() {
    changePassword.mutate(
      { old_password: oldPassword, new_password: newPassword },
      {
        onSuccess: () => {
          toast.success("Password changed successfully");
          setOldPassword("");
          setNewPassword("");
        },
        onError: (err) => toast.error(getErrorMessage(err)),
      },
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-bold text-surface-900 dark:text-surface-100">
          Settings
        </h1>
        <p className="text-surface-500 dark:text-surface-400">
          Manage your account settings and preferences
        </p>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Appearance</CardTitle>
        </CardHeader>
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-3">
            {isDark ? <Moon className="h-5 w-5 text-surface-500" /> : <Sun className="h-5 w-5 text-surface-500" />}
            <div>
              <p className="font-medium text-surface-900 dark:text-surface-100">Dark Mode</p>
              <p className="text-sm text-surface-500">Toggle dark mode for the entire application</p>
            </div>
          </div>
          <button
            onClick={toggle}
            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
              isDark ? "bg-brand-600" : "bg-surface-300"
            }`}
            role="switch"
            aria-checked={isDark}
            aria-label="Toggle dark mode"
          >
            <span
              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                isDark ? "translate-x-6" : "translate-x-1"
              }`}
            />
          </button>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Change Password</CardTitle>
        </CardHeader>
        <div className="space-y-4 max-w-md">
          <Input
            label="Current Password"
            type="password"
            value={oldPassword}
            onChange={(e) => setOldPassword(e.target.value)}
          />
          <Input
            label="New Password"
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            helperText="Min 12 characters with uppercase, lowercase, digit, and special character"
          />
          <Button
            onClick={handleChangePassword}
            isLoading={changePassword.isPending}
            leftIcon={<Save className="h-4 w-4" />}
          >
            Update Password
          </Button>
        </div>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Notifications</CardTitle>
        </CardHeader>
        <div className="space-y-4">
          {[
            { label: "Assessment reminders", description: "Get notified before assessment due dates" },
            { label: "Regulation updates", description: "When regulations are added or updated" },
            { label: "Finding assignments", description: "When findings are assigned to you" },
          ].map((item) => (
            <div key={item.label} className="flex items-center justify-between">
              <div>
                <p className="font-medium text-surface-900 dark:text-surface-100">{item.label}</p>
                <p className="text-sm text-surface-500">{item.description}</p>
              </div>
              <button
                className="relative inline-flex h-6 w-11 items-center rounded-full bg-brand-600 transition-colors"
                role="switch"
                aria-checked="true"
                aria-label={`Toggle ${item.label}`}
              >
                <span className="inline-block h-4 w-4 translate-x-6 transform rounded-full bg-white" />
              </button>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

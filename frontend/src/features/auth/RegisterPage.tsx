import { useState } from "react";
import { Link, Navigate, useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { z } from "zod";
import { Eye, EyeOff, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Input } from "@/components/ui/Input";
import { Card, CardTitle } from "@/components/ui/Card";
import { useRegister, getErrorMessage } from "@/hooks/useAuth";
import { useAppSelector } from "@/app/hooks";
import toast from "react-hot-toast";

const registerSchema = z
  .object({
    email: z.string().email("Please enter a valid email"),
    username: z
      .string()
      .min(3, "Username must be at least 3 characters")
      .max(150, "Username is too long"),
    password: z
      .string()
      .min(12, "Password must be at least 12 characters")
      .max(128, "Password is too long")
      .regex(/[A-Z]/, "Password must contain an uppercase letter")
      .regex(/[a-z]/, "Password must contain a lowercase letter")
      .regex(/[0-9]/, "Password must contain a digit")
      .regex(/[^A-Za-z0-9]/, "Password must contain a special character"),
    confirmPassword: z.string(),
    full_name: z.string().optional(),
  })
  .refine((data) => data.password === data.confirmPassword, {
    message: "Passwords do not match",
    path: ["confirmPassword"],
  });

type RegisterForm = z.infer<typeof registerSchema>;

export function RegisterPage() {
  const { isAuthenticated } = useAppSelector((s) => s.auth);
  const registerMutation = useRegister();
  const navigate = useNavigate();
  const [showPassword, setShowPassword] = useState(false);

  const {
    register,
    handleSubmit,
    formState: { errors },
  } = useForm<RegisterForm>({
    resolver: zodResolver(registerSchema),
  });

  async function onSubmit(data: RegisterForm) {
    try {
      await registerMutation.mutateAsync({
        email: data.email,
        username: data.username,
        password: data.password,
        full_name: data.full_name || null,
      });
      toast.success("Account created! You can now sign in.");
      navigate("/login");
    } catch {
      // error handled via mutation state
    }
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-br from-brand-50 via-white to-surface-50 px-4 dark:from-surface-950 dark:via-surface-900 dark:to-surface-950">
      <div className="w-full max-w-md animate-fade-in">
        <div className="mb-8 text-center">
          <h1 className="text-3xl font-bold text-brand-600 dark:text-brand-400">
            RegulaForge
          </h1>
          <p className="mt-2 text-surface-500 dark:text-surface-400">
            Create your account
          </p>
        </div>

        <Card padding="lg">
          <CardTitle className="mb-6 text-center">Create account</CardTitle>

          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <Input
              label="Email"
              type="email"
              placeholder="you@company.com"
              error={errors.email?.message}
              {...register("email")}
            />
            <Input
              label="Username"
              placeholder="johndoe"
              error={errors.username?.message}
              {...register("username")}
            />
            <Input
              label="Full name (optional)"
              placeholder="John Doe"
              error={errors.full_name?.message}
              {...register("full_name")}
            />

            <div className="relative">
              <Input
                label="Password"
                type={showPassword ? "text" : "password"}
                placeholder="At least 12 characters"
                error={errors.password?.message}
                {...register("password")}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="absolute right-3 top-[38px] text-surface-400 hover:text-surface-600"
                aria-label={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
              </button>
            </div>

            <Input
              label="Confirm password"
              type="password"
              placeholder="Repeat your password"
              error={errors.confirmPassword?.message}
              {...register("confirmPassword")}
            />

            {registerMutation.isError && (
              <div
                className="rounded-lg bg-red-50 px-4 py-3 text-sm text-red-600 dark:bg-red-950/30 dark:text-red-400"
                role="alert"
              >
                {getErrorMessage(registerMutation.error)}
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              size="lg"
              isLoading={registerMutation.isPending}
              leftIcon={<UserPlus className="h-4 w-4" />}
            >
              Create account
            </Button>
          </form>

          <p className="mt-6 text-center text-sm text-surface-500 dark:text-surface-400">
            Already have an account?{" "}
            <Link
              to="/login"
              className="font-medium text-brand-600 hover:text-brand-500 dark:text-brand-400"
            >
              Sign in
            </Link>
          </p>
        </Card>
      </div>
    </div>
  );
}

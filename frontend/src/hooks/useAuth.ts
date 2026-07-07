import { useMutation, useQuery } from "@tanstack/react-query";
import { useAppDispatch, useAppSelector } from "@/app/hooks";
import { clearAuth, setUser } from "@/stores/authSlice";
import apiClient, { getErrorMessage } from "@/lib/api-client";
import type {
  ChangePasswordRequest,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  User,
} from "@/types/auth";

export function useCurrentUser() {
  const dispatch = useAppDispatch();
  const { user, isAuthenticated } = useAppSelector((s) => s.auth);

  return useQuery({
    queryKey: ["current-user"],
    queryFn: async () => {
      const { data } = await apiClient.get<User>("/auth/me");
      dispatch(setUser(data));
      return data;
    },
    enabled: isAuthenticated,
    retry: false,
    staleTime: 5 * 60 * 1000,
    initialData: user ?? undefined,
  });
}

export function useLogin() {
  const dispatch = useAppDispatch();

  return useMutation({
    mutationFn: async (credentials: LoginRequest) => {
      const { data } = await apiClient.post<TokenResponse>(
        "/auth/login",
        credentials,
      );
      localStorage.setItem("access_token", data.access_token);
      localStorage.setItem("refresh_token", data.refresh_token);
      dispatch(setUser(data.user));
      return data;
    },
  });
}

export function useRegister() {
  return useMutation({
    mutationFn: async (payload: RegisterRequest) => {
      const { data } = await apiClient.post<User>("/auth/register", payload);
      return data;
    },
  });
}

export function useLogout() {
  const dispatch = useAppDispatch();

  return () => {
    dispatch(clearAuth());
    window.location.href = "/login";
  };
}

export function useChangePassword() {
  return useMutation({
    mutationFn: async (payload: ChangePasswordRequest) => {
      const { data } = await apiClient.post("/auth/change-password", payload);
      return data;
    },
  });
}

export { getErrorMessage };

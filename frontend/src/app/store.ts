import { configureStore } from "@reduxjs/toolkit";
import authReducer from "@/stores/authSlice";
import uiReducer from "@/stores/uiSlice";

export const store = configureStore({
  reducer: {
    auth: authReducer,
    ui: uiReducer,
  },
});

export type RootState = ReturnType<typeof store.getState>;
export type AppDispatch = typeof store.dispatch;

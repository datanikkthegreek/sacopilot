import { useQuery, useSuspenseQuery, useMutation } from "@tanstack/react-query";
import type { UseQueryOptions, UseSuspenseQueryOptions, UseMutationOptions } from "@tanstack/react-query";
export class ApiError extends Error {
    status: number;
    statusText: string;
    body: unknown;
    constructor(status: number, statusText: string, body: unknown){
        super(`HTTP ${status}: ${statusText}`);
        this.name = "ApiError";
        this.status = status;
        this.statusText = statusText;
        this.body = body;
    }
}
export interface ApprovalDecision {
    decision: string;
    edited_args?: Record<string, unknown> | null;
    id: string;
}
export interface ComplexValue {
    display?: string | null;
    primary?: boolean | null;
    ref?: string | null;
    type?: string | null;
    value?: string | null;
}
export interface FacetEdit {
    bosch?: string | null;
    bu?: string[];
    dbx?: string | null;
    org: string;
    prio: string;
    type: string;
}
export interface GenerateIn {
    artifact: string;
    prompt?: string;
}
export interface HTTPValidationError {
    detail?: ValidationError[];
}
export interface MessageRequest {
    history?: Record<string, unknown>[] | null;
    message: string;
}
export interface Name {
    family_name?: string | null;
    given_name?: string | null;
}
export interface SendIn {
    body: string;
    draft_id?: string | null;
    reply_to_message_id?: string | null;
    subject: string;
    to: string;
}
export interface StatusEdit {
    status: string;
}
export interface UpdateIn {
    next_steps?: string | null;
    onboarding?: string | null;
}
export interface User {
    active?: boolean | null;
    display_name?: string | null;
    emails?: ComplexValue[] | null;
    entitlements?: ComplexValue[] | null;
    external_id?: string | null;
    groups?: ComplexValue[] | null;
    id?: string | null;
    name?: Name | null;
    roles?: ComplexValue[] | null;
    schemas?: UserSchema[] | null;
    user_name?: string | null;
}
export const UserSchema = {
    "urn:ietf:params:scim:schemas:core:2.0:User": "urn:ietf:params:scim:schemas:core:2.0:User",
    "urn:ietf:params:scim:schemas:extension:workspace:2.0:User": "urn:ietf:params:scim:schemas:extension:workspace:2.0:User"
} as const;
export type UserSchema = typeof UserSchema[keyof typeof UserSchema];
export interface ValidationError {
    ctx?: Record<string, unknown>;
    input?: unknown;
    loc: (string | number)[];
    msg: string;
    type: string;
}
export interface VersionOut {
    version: string;
}
export const agent_approve_api_agent_approve_post = async (data: ApprovalDecision, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch("/api/agent/approve", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useAgent_approve_api_agent_approve_post(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, ApprovalDecision>;
}) {
    return useMutation({
        mutationFn: (data)=>agent_approve_api_agent_approve_post(data),
        ...options?.mutation
    });
}
export const agent_message_api_agent_message_post = async (data: MessageRequest, options?: RequestInit): Promise<{
    data: unknown;
}> =>{
    const res = await fetch("/api/agent/message", {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useAgent_message_api_agent_message_post(options?: {
    mutation?: UseMutationOptions<{
        data: unknown;
    }, ApiError, MessageRequest>;
}) {
    return useMutation({
        mutationFn: (data)=>agent_message_api_agent_message_post(data),
        ...options?.mutation
    });
}
export const agent_pending_api_agent_pending_get = async (options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch("/api/agent/pending", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const agent_pending_api_agent_pending_getKey = ()=>{
    return [
        "/api/agent/pending"
    ] as const;
};
export function useAgent_pending_api_agent_pending_get<TData = {
    data: Record<string, unknown>;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: agent_pending_api_agent_pending_getKey(),
        queryFn: ()=>agent_pending_api_agent_pending_get(),
        ...options?.query
    });
}
export function useAgent_pending_api_agent_pending_getSuspense<TData = {
    data: Record<string, unknown>;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: agent_pending_api_agent_pending_getKey(),
        queryFn: ()=>agent_pending_api_agent_pending_get(),
        ...options?.query
    });
}
export interface CurrentUserParams {
    "X-Forwarded-Host"?: string | null;
    "X-Forwarded-Preferred-Username"?: string | null;
    "X-Forwarded-User"?: string | null;
    "X-Forwarded-Email"?: string | null;
    "X-Request-Id"?: string | null;
    "X-Forwarded-Access-Token"?: string | null;
}
export const currentUser = async (params?: CurrentUserParams, options?: RequestInit): Promise<{
    data: User;
}> =>{
    const res = await fetch("/api/current-user", {
        ...options,
        method: "GET",
        headers: {
            ...(params?.["X-Forwarded-Host"] != null && {
                "X-Forwarded-Host": params["X-Forwarded-Host"]
            }),
            ...(params?.["X-Forwarded-Preferred-Username"] != null && {
                "X-Forwarded-Preferred-Username": params["X-Forwarded-Preferred-Username"]
            }),
            ...(params?.["X-Forwarded-User"] != null && {
                "X-Forwarded-User": params["X-Forwarded-User"]
            }),
            ...(params?.["X-Forwarded-Email"] != null && {
                "X-Forwarded-Email": params["X-Forwarded-Email"]
            }),
            ...(params?.["X-Request-Id"] != null && {
                "X-Request-Id": params["X-Request-Id"]
            }),
            ...(params?.["X-Forwarded-Access-Token"] != null && {
                "X-Forwarded-Access-Token": params["X-Forwarded-Access-Token"]
            }),
            ...options?.headers
        }
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const currentUserKey = (params?: CurrentUserParams)=>{
    return [
        "/api/current-user",
        params
    ] as const;
};
export function useCurrentUser<TData = {
    data: User;
}>(options?: {
    params?: CurrentUserParams;
    query?: Omit<UseQueryOptions<{
        data: User;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: currentUserKey(options?.params),
        queryFn: ()=>currentUser(options?.params),
        ...options?.query
    });
}
export function useCurrentUserSuspense<TData = {
    data: User;
}>(options?: {
    params?: CurrentUserParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: User;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: currentUserKey(options?.params),
        queryFn: ()=>currentUser(options?.params),
        ...options?.query
    });
}
export const mail_classify_api_mail_classify_post = async (options?: RequestInit): Promise<{
    data: unknown;
}> =>{
    const res = await fetch("/api/mail/classify", {
        ...options,
        method: "POST"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMail_classify_api_mail_classify_post(options?: {
    mutation?: UseMutationOptions<{
        data: unknown;
    }, ApiError, void>;
}) {
    return useMutation({
        mutationFn: ()=>mail_classify_api_mail_classify_post(),
        ...options?.mutation
    });
}
export interface Mail_update_api_mail_classify__thread_id__putParams {
    thread_id: string;
}
export const mail_update_api_mail_classify__thread_id__put = async (params: Mail_update_api_mail_classify__thread_id__putParams, data: FacetEdit, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/mail/classify/${params.thread_id}`, {
        ...options,
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMail_update_api_mail_classify__thread_id__put(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: Mail_update_api_mail_classify__thread_id__putParams;
        data: FacetEdit;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>mail_update_api_mail_classify__thread_id__put(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface Mail_reply_api_mail_reply__thread_id__postParams {
    thread_id: string;
}
export const mail_reply_api_mail_reply__thread_id__post = async (params: Mail_reply_api_mail_reply__thread_id__postParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/mail/reply/${params.thread_id}`, {
        ...options,
        method: "POST"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMail_reply_api_mail_reply__thread_id__post(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: Mail_reply_api_mail_reply__thread_id__postParams;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>mail_reply_api_mail_reply__thread_id__post(vars.params),
        ...options?.mutation
    });
}
export interface Mail_send_api_mail_send__thread_id__postParams {
    thread_id: string;
}
export const mail_send_api_mail_send__thread_id__post = async (params: Mail_send_api_mail_send__thread_id__postParams, data: SendIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/mail/send/${params.thread_id}`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMail_send_api_mail_send__thread_id__post(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: Mail_send_api_mail_send__thread_id__postParams;
        data: SendIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>mail_send_api_mail_send__thread_id__post(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface Mail_status_api_mail_status__thread_id__putParams {
    thread_id: string;
}
export const mail_status_api_mail_status__thread_id__put = async (params: Mail_status_api_mail_status__thread_id__putParams, data: StatusEdit, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/mail/status/${params.thread_id}`, {
        ...options,
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMail_status_api_mail_status__thread_id__put(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: Mail_status_api_mail_status__thread_id__putParams;
        data: StatusEdit;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>mail_status_api_mail_status__thread_id__put(vars.params, vars.data),
        ...options?.mutation
    });
}
export const mail_sync_api_mail_sync_post = async (options?: RequestInit): Promise<{
    data: unknown;
}> =>{
    const res = await fetch("/api/mail/sync", {
        ...options,
        method: "POST"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMail_sync_api_mail_sync_post(options?: {
    mutation?: UseMutationOptions<{
        data: unknown;
    }, ApiError, void>;
}) {
    return useMutation({
        mutationFn: ()=>mail_sync_api_mail_sync_post(),
        ...options?.mutation
    });
}
export const mail_taxonomy_api_mail_taxonomy_get = async (options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch("/api/mail/taxonomy", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const mail_taxonomy_api_mail_taxonomy_getKey = ()=>{
    return [
        "/api/mail/taxonomy"
    ] as const;
};
export function useMail_taxonomy_api_mail_taxonomy_get<TData = {
    data: Record<string, unknown>;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: mail_taxonomy_api_mail_taxonomy_getKey(),
        queryFn: ()=>mail_taxonomy_api_mail_taxonomy_get(),
        ...options?.query
    });
}
export function useMail_taxonomy_api_mail_taxonomy_getSuspense<TData = {
    data: Record<string, unknown>;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: mail_taxonomy_api_mail_taxonomy_getKey(),
        queryFn: ()=>mail_taxonomy_api_mail_taxonomy_get(),
        ...options?.query
    });
}
export interface Mail_thread_api_mail_thread__thread_id__getParams {
    thread_id: string;
}
export const mail_thread_api_mail_thread__thread_id__get = async (params: Mail_thread_api_mail_thread__thread_id__getParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/mail/thread/${params.thread_id}`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const mail_thread_api_mail_thread__thread_id__getKey = (params?: Mail_thread_api_mail_thread__thread_id__getParams)=>{
    return [
        "/api/mail/thread/{thread_id}",
        params
    ] as const;
};
export function useMail_thread_api_mail_thread__thread_id__get<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: Mail_thread_api_mail_thread__thread_id__getParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: mail_thread_api_mail_thread__thread_id__getKey(options.params),
        queryFn: ()=>mail_thread_api_mail_thread__thread_id__get(options.params),
        ...options?.query
    });
}
export function useMail_thread_api_mail_thread__thread_id__getSuspense<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: Mail_thread_api_mail_thread__thread_id__getParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: mail_thread_api_mail_thread__thread_id__getKey(options.params),
        queryFn: ()=>mail_thread_api_mail_thread__thread_id__get(options.params),
        ...options?.query
    });
}
export interface Mail_threads_api_mail_threads_getParams {
    limit?: number;
    offset?: number;
    unread?: boolean;
    status?: string | null;
    label?: string | null;
}
export const mail_threads_api_mail_threads_get = async (params?: Mail_threads_api_mail_threads_getParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.limit != null) searchParams.set("limit", String(params?.limit));
    if (params?.offset != null) searchParams.set("offset", String(params?.offset));
    if (params?.unread != null) searchParams.set("unread", String(params?.unread));
    if (params?.status != null) searchParams.set("status", String(params?.status));
    if (params?.label != null) searchParams.set("label", String(params?.label));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/mail/threads?${queryString}` : "/api/mail/threads";
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const mail_threads_api_mail_threads_getKey = (params?: Mail_threads_api_mail_threads_getParams)=>{
    return [
        "/api/mail/threads",
        params
    ] as const;
};
export function useMail_threads_api_mail_threads_get<TData = {
    data: Record<string, unknown>;
}>(options?: {
    params?: Mail_threads_api_mail_threads_getParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: mail_threads_api_mail_threads_getKey(options?.params),
        queryFn: ()=>mail_threads_api_mail_threads_get(options?.params),
        ...options?.query
    });
}
export function useMail_threads_api_mail_threads_getSuspense<TData = {
    data: Record<string, unknown>;
}>(options?: {
    params?: Mail_threads_api_mail_threads_getParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: mail_threads_api_mail_threads_getKey(options?.params),
        queryFn: ()=>mail_threads_api_mail_threads_get(options?.params),
        ...options?.query
    });
}
export interface Meetings_categorize_api_meetings_categorize_postParams {
    start?: string | null;
}
export const meetings_categorize_api_meetings_categorize_post = async (params?: Meetings_categorize_api_meetings_categorize_postParams, options?: RequestInit): Promise<{
    data: unknown;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.start != null) searchParams.set("start", String(params?.start));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/meetings/categorize?${queryString}` : "/api/meetings/categorize";
    const res = await fetch(url, {
        ...options,
        method: "POST"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useMeetings_categorize_api_meetings_categorize_post(options?: {
    mutation?: UseMutationOptions<{
        data: unknown;
    }, ApiError, {
        params: Meetings_categorize_api_meetings_categorize_postParams;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>meetings_categorize_api_meetings_categorize_post(vars.params),
        ...options?.mutation
    });
}
export const meetings_today_api_meetings_today_get = async (options?: RequestInit): Promise<{
    data: Record<string, unknown>[];
}> =>{
    const res = await fetch("/api/meetings/today", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const meetings_today_api_meetings_today_getKey = ()=>{
    return [
        "/api/meetings/today"
    ] as const;
};
export function useMeetings_today_api_meetings_today_get<TData = {
    data: Record<string, unknown>[];
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: meetings_today_api_meetings_today_getKey(),
        queryFn: ()=>meetings_today_api_meetings_today_get(),
        ...options?.query
    });
}
export function useMeetings_today_api_meetings_today_getSuspense<TData = {
    data: Record<string, unknown>[];
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>[];
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: meetings_today_api_meetings_today_getKey(),
        queryFn: ()=>meetings_today_api_meetings_today_get(),
        ...options?.query
    });
}
export interface Meetings_week_api_meetings_week_getParams {
    start?: string | null;
}
export const meetings_week_api_meetings_week_get = async (params?: Meetings_week_api_meetings_week_getParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.start != null) searchParams.set("start", String(params?.start));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/meetings/week?${queryString}` : "/api/meetings/week";
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const meetings_week_api_meetings_week_getKey = (params?: Meetings_week_api_meetings_week_getParams)=>{
    return [
        "/api/meetings/week",
        params
    ] as const;
};
export function useMeetings_week_api_meetings_week_get<TData = {
    data: Record<string, unknown>;
}>(options?: {
    params?: Meetings_week_api_meetings_week_getParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: meetings_week_api_meetings_week_getKey(options?.params),
        queryFn: ()=>meetings_week_api_meetings_week_get(options?.params),
        ...options?.query
    });
}
export function useMeetings_week_api_meetings_week_getSuspense<TData = {
    data: Record<string, unknown>;
}>(options?: {
    params?: Meetings_week_api_meetings_week_getParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: meetings_week_api_meetings_week_getKey(options?.params),
        queryFn: ()=>meetings_week_api_meetings_week_get(options?.params),
        ...options?.query
    });
}
export interface Usecases_list_api_usecases_getParams {
    account?: string;
    prefix?: string;
}
export const usecases_list_api_usecases_get = async (params?: Usecases_list_api_usecases_getParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const searchParams = new URLSearchParams();
    if (params?.account != null) searchParams.set("account", String(params?.account));
    if (params?.prefix != null) searchParams.set("prefix", String(params?.prefix));
    const queryString = searchParams.toString();
    const url = queryString ? `/api/usecases?${queryString}` : "/api/usecases";
    const res = await fetch(url, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const usecases_list_api_usecases_getKey = (params?: Usecases_list_api_usecases_getParams)=>{
    return [
        "/api/usecases",
        params
    ] as const;
};
export function useUsecases_list_api_usecases_get<TData = {
    data: Record<string, unknown>;
}>(options?: {
    params?: Usecases_list_api_usecases_getParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: usecases_list_api_usecases_getKey(options?.params),
        queryFn: ()=>usecases_list_api_usecases_get(options?.params),
        ...options?.query
    });
}
export function useUsecases_list_api_usecases_getSuspense<TData = {
    data: Record<string, unknown>;
}>(options?: {
    params?: Usecases_list_api_usecases_getParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: usecases_list_api_usecases_getKey(options?.params),
        queryFn: ()=>usecases_list_api_usecases_get(options?.params),
        ...options?.query
    });
}
export interface Usecase_detail_api_usecases__uco_id__getParams {
    uco_id: string;
}
export const usecase_detail_api_usecases__uco_id__get = async (params: Usecase_detail_api_usecases__uco_id__getParams, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/usecases/${params.uco_id}`, {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const usecase_detail_api_usecases__uco_id__getKey = (params?: Usecase_detail_api_usecases__uco_id__getParams)=>{
    return [
        "/api/usecases/{uco_id}",
        params
    ] as const;
};
export function useUsecase_detail_api_usecases__uco_id__get<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: Usecase_detail_api_usecases__uco_id__getParams;
    query?: Omit<UseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: usecase_detail_api_usecases__uco_id__getKey(options.params),
        queryFn: ()=>usecase_detail_api_usecases__uco_id__get(options.params),
        ...options?.query
    });
}
export function useUsecase_detail_api_usecases__uco_id__getSuspense<TData = {
    data: Record<string, unknown>;
}>(options: {
    params: Usecase_detail_api_usecases__uco_id__getParams;
    query?: Omit<UseSuspenseQueryOptions<{
        data: Record<string, unknown>;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: usecase_detail_api_usecases__uco_id__getKey(options.params),
        queryFn: ()=>usecase_detail_api_usecases__uco_id__get(options.params),
        ...options?.query
    });
}
export interface Usecase_update_api_usecases__uco_id__putParams {
    uco_id: string;
}
export const usecase_update_api_usecases__uco_id__put = async (params: Usecase_update_api_usecases__uco_id__putParams, data: UpdateIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/usecases/${params.uco_id}`, {
        ...options,
        method: "PUT",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useUsecase_update_api_usecases__uco_id__put(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: Usecase_update_api_usecases__uco_id__putParams;
        data: UpdateIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>usecase_update_api_usecases__uco_id__put(vars.params, vars.data),
        ...options?.mutation
    });
}
export interface Usecase_generate_api_usecases__uco_id__generate_postParams {
    uco_id: string;
}
export const usecase_generate_api_usecases__uco_id__generate_post = async (params: Usecase_generate_api_usecases__uco_id__generate_postParams, data: GenerateIn, options?: RequestInit): Promise<{
    data: Record<string, unknown>;
}> =>{
    const res = await fetch(`/api/usecases/${params.uco_id}/generate`, {
        ...options,
        method: "POST",
        headers: {
            "Content-Type": "application/json",
            ...options?.headers
        },
        body: JSON.stringify(data)
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export function useUsecase_generate_api_usecases__uco_id__generate_post(options?: {
    mutation?: UseMutationOptions<{
        data: Record<string, unknown>;
    }, ApiError, {
        params: Usecase_generate_api_usecases__uco_id__generate_postParams;
        data: GenerateIn;
    }>;
}) {
    return useMutation({
        mutationFn: (vars)=>usecase_generate_api_usecases__uco_id__generate_post(vars.params, vars.data),
        ...options?.mutation
    });
}
export const version = async (options?: RequestInit): Promise<{
    data: VersionOut;
}> =>{
    const res = await fetch("/api/version", {
        ...options,
        method: "GET"
    });
    if (!res.ok) {
        const body = await res.text();
        let parsed: unknown;
        try {
            parsed = JSON.parse(body);
        } catch  {
            parsed = body;
        }
        throw new ApiError(res.status, res.statusText, parsed);
    }
    return {
        data: await res.json()
    };
};
export const versionKey = ()=>{
    return [
        "/api/version"
    ] as const;
};
export function useVersion<TData = {
    data: VersionOut;
}>(options?: {
    query?: Omit<UseQueryOptions<{
        data: VersionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useQuery({
        queryKey: versionKey(),
        queryFn: ()=>version(),
        ...options?.query
    });
}
export function useVersionSuspense<TData = {
    data: VersionOut;
}>(options?: {
    query?: Omit<UseSuspenseQueryOptions<{
        data: VersionOut;
    }, ApiError, TData>, "queryKey" | "queryFn">;
}) {
    return useSuspenseQuery({
        queryKey: versionKey(),
        queryFn: ()=>version(),
        ...options?.query
    });
}

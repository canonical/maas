import { http, HttpResponse } from "msw";

import { BASE_URL } from "../utils";

import type {
  CreateUserError,
  DeleteUserError,
  GetUserError,
  ListUsersError,
  ListUsersResponse,
  ListUsersStatisticsError,
  ListUsersStatisticsResponse,
  UpdateUserError,
} from "@/app/apiclient";
import {
  user as userFactory,
  userStatistics as userStatisticsFactory,
} from "@/testing/factories";

const mockUsers: ListUsersResponse = {
  items: [
    userFactory({
      id: 1,
      email: "user1@example.com",
      username: "user1",
    }),
    userFactory({
      id: 2,
      email: "user2@example.com",
      username: "user2",
    }),
    userFactory({
      id: 3,
      email: "user3@example.com",
      username: "user3",
    }),
  ],
  total: 3,
};

const mockUsersStatistics: ListUsersStatisticsResponse = {
  items: [
    userStatisticsFactory({
      id: 1,
    }),
    userStatisticsFactory({
      id: 2,
    }),
    userStatisticsFactory({
      id: 3,
    }),
  ],
  total: 3,
};

const mockListUsersError: ListUsersError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error", // This will always be 'Error' for every error response
};

const mockListUsersStatisticsError: ListUsersStatisticsError = {
  message: "Unauthorized",
  code: 401,
  kind: "Error",
};

const mockGetUserError: GetUserError = {
  message: "Not found",
  code: 404,
  kind: "Error",
};

const mockCreateUserError: CreateUserError = {
  message: "A user with this name already exists.",
  code: 409,
  kind: "Error",
};

const mockUpdateUserError: UpdateUserError = {
  message: "Internal server error",
  code: 500,
  kind: "Error",
};

const usersResolvers = {
  listUsers: {
    resolved: false,
    handler: (data: ListUsersResponse = mockUsers) =>
      http.get(`${BASE_URL}MAAS/a/v3/users`, () => {
        usersResolvers.listUsers.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListUsersError = mockListUsersError) =>
      http.get(`${BASE_URL}MAAS/a/v3/users`, () => {
        usersResolvers.listUsers.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  listUsersStatistics: {
    resolved: false,
    handler: (data: ListUsersStatisticsResponse = mockUsersStatistics) =>
      http.get(`${BASE_URL}MAAS/a/v3/users\:statistics`, () => {
        usersResolvers.listUsersStatistics.resolved = true;
        return HttpResponse.json(data);
      }),
    error: (error: ListUsersStatisticsError = mockListUsersStatisticsError) =>
      http.get(`${BASE_URL}MAAS/a/v3/users\:statistics`, () => {
        usersResolvers.listUsersStatistics.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  getUser: {
    resolved: false,
    handler: () =>
      http.get(`${BASE_URL}MAAS/a/v3/users/:id`, ({ params }) => {
        const id = Number(params.id);
        if (!id) return HttpResponse.error();

        const user = mockUsers.items.find((user) => user.id === id);
        usersResolvers.getUser.resolved = true;
        return user ? HttpResponse.json(user) : HttpResponse.error();
      }),
    error: (error: GetUserError = mockGetUserError) =>
      http.get(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.getUser.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  createUser: {
    resolved: false,
    handler: () =>
      http.post(`${BASE_URL}MAAS/a/v3/users`, () => {
        usersResolvers.createUser.resolved = true;
        return HttpResponse.json({ id: 1 });
      }),
    error: (error: CreateUserError = mockCreateUserError) =>
      http.post(`${BASE_URL}MAAS/a/v3/users`, () => {
        usersResolvers.createUser.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  updateUser: {
    resolved: false,
    handler: () =>
      http.put(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.updateUser.resolved = true;
        return HttpResponse.json({});
      }),
    error: (error: UpdateUserError = mockUpdateUserError) =>
      http.put(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.updateUser.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
  deleteUser: {
    resolved: false,
    handler: () =>
      http.delete(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.deleteUser.resolved = true;
        return HttpResponse.json({}, { status: 204 });
      }),
    error: (error: DeleteUserError = mockGetUserError) =>
      http.delete(`${BASE_URL}MAAS/a/v3/users/:id`, () => {
        usersResolvers.deleteUser.resolved = true;
        return HttpResponse.json(error, { status: error.code });
      }),
  },
};

export { mockUsers, mockUsersStatistics, usersResolvers };

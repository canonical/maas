import { define, random } from "cooky-cutter";

import type { UserResponse, UserStatisticsResponse } from "@/app/apiclient";
import { timestamp } from "@/testing/factories/general";

export const user = define<UserResponse>({
  id: random,
  email: (i: number) => `email${i}@example.com`,
  is_superuser: true,
  last_name: "MAAS",
  first_name: "John",
  date_joined: () => timestamp("Fri, 23 Oct. 2020 00:00:00"),
  last_login: () => timestamp("Fri, 23 Oct. 2020 00:00:00"),
  username: (i: number) => `user${i}`,
});

export const userStatistics = define<UserStatisticsResponse>({
  id: random,
  completed_intro: true,
  is_local: true,
  machines_count: random,
  sshkeys_count: random,
});

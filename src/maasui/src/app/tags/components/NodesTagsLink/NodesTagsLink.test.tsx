import NodesTagsLink from "./NodesTagsLink";

import urls from "@/app/base/urls";
import { ControllerMeta } from "@/app/store/controller/types";
import { DeviceMeta } from "@/app/store/device/types";
import { MachineMeta } from "@/app/store/machine/types";
import { renderWithProviders, screen } from "@/testing/utils";

it("create a link to machines", () => {
  renderWithProviders(
    <NodesTagsLink count={1} nodeType={MachineMeta.MODEL} tags={["a-tag"]} />
  );
  const machineLink = screen.getByRole("link", {
    name: "1 machine",
  });
  expect(machineLink).toBeInTheDocument();
  expect(machineLink).toHaveAttribute(
    "href",
    `${urls.machines.index}?tags=%3Da-tag`
  );
});

it("create a link to controllers", () => {
  renderWithProviders(
    <NodesTagsLink count={3} nodeType={ControllerMeta.MODEL} tags={["a-tag"]} />
  );
  const controllerLink = screen.getByRole("link", {
    name: "3 controllers",
  });
  expect(controllerLink).toBeInTheDocument();
  expect(controllerLink).toHaveAttribute(
    "href",
    `${urls.controllers.index}?tags=%3Da-tag`
  );
});

it("create a link to devices", () => {
  renderWithProviders(
    <NodesTagsLink count={2} nodeType={DeviceMeta.MODEL} tags={["a-tag"]} />
  );
  const deviceLink = screen.getByRole("link", {
    name: "2 devices",
  });
  expect(deviceLink).toBeInTheDocument();
  expect(deviceLink).toHaveAttribute(
    "href",
    `${urls.devices.index}?tags=%3Da-tag`
  );
});

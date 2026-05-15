import { Formik } from "formik";

import { MaasIntroSchema } from "../MaasIntro";

import NameCard, { Labels as NameCardLabels } from "./NameCard";

import { ConfigNames } from "@/app/store/config/types";
import type { RootState } from "@/app/store/root/types";
import * as factory from "@/testing/factories";
import { authResolvers } from "@/testing/resolvers/auth";
import {
  renderWithProviders,
  screen,
  setupMockServer,
  userEvent,
} from "@/testing/utils";

setupMockServer(
  authResolvers.getCurrentUser.handler(),
  authResolvers.getMeStatistics.handler()
);

describe("NameCard", () => {
  let state: RootState;
  beforeEach(() => {
    state = factory.rootState({
      config: factory.configState({
        items: [
          factory.config({ name: ConfigNames.COMPLETED_INTRO, value: false }),
          factory.config({ name: ConfigNames.MAAS_NAME, value: "bionic-maas" }),
        ],
      }),
    });
  });

  it("displays a tick when there are no name errors", () => {
    renderWithProviders(
      <Formik initialValues={{ name: "my new maas" }} onSubmit={vi.fn()}>
        <NameCard />
      </Formik>,
      { state }
    );
    const icon = screen.getByLabelText("success");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("p-icon--success");
  });

  it("displays an error icon when there are name errors", async () => {
    renderWithProviders(
      <Formik
        initialValues={{ name: "my new maas" }}
        onSubmit={vi.fn()}
        validationSchema={MaasIntroSchema}
      >
        <NameCard />
      </Formik>,
      { state }
    );
    await userEvent.clear(
      screen.getByRole("textbox", { name: NameCardLabels.Name })
    );
    await userEvent.tab();

    const icon = screen.getByLabelText("error");
    expect(icon).toBeInTheDocument();
    expect(icon).toHaveClass("p-icon--error");
  });
});

import type { ReactElement } from "react";
import { useState } from "react";

import {
  Button,
  Notification as NotificationBanner,
  Spinner,
} from "@canonical/react-components";
import { useQueryClient } from "@tanstack/react-query";
import * as Yup from "yup";

import { Labels } from "../../constants";

import { useAuthenticate } from "@/app/api/query/auth";
import { useGetUser, useUpdateUser } from "@/app/api/query/users";
import type { UpdateUserError, UserUpdateRequest } from "@/app/apiclient";
import { getUserQueryKey } from "@/app/apiclient/@tanstack/react-query.gen";
import FormikField from "@/app/base/components/FormikField";
import FormikForm from "@/app/base/components/FormikForm";
import { useSidePanel } from "@/app/base/side-panel-context";

type EditUserProps = {
  id: number;
  isSelfEditing?: boolean;
};

const UserSchema = Yup.object().shape({
  email: Yup.string()
    .email("Must be a valid email address")
    .required("Email is required"),
  fullName: Yup.string(),
  is_superuser: Yup.boolean(),
  password: Yup.string(),
  passwordConfirm: Yup.string().oneOf(
    [Yup.ref("password")],
    "Passwords must be the same"
  ),
  username: Yup.string()
    .max(150, "Username must be 150 characters or less")
    .matches(
      /^[a-zA-Z 0-9@.+-_]*$/,
      "Usernames must contain letters, digits and @/./+/-/_ only"
    )
    .required("Username is required"),
});

const SelfEditUserSchema = UserSchema.shape({
  oldPassword: Yup.string().required("Your current password is required"),
  password: Yup.string().required("A new password is required"),
  passwordConfirm: Yup.string().required("Confirm your new password"),
});

const EditUser = ({
  id,
  isSelfEditing = false,
}: EditUserProps): ReactElement => {
  const { closeSidePanel } = useSidePanel();
  const queryClient = useQueryClient();
  const [passwordVisible, setPasswordVisible] = useState(false);
  const [authError, setAuthError] = useState<string | null>(null);

  const authenticate = useAuthenticate();
  const user = useGetUser({ path: { user_id: id } });
  const eTag = user.data?.headers?.get("ETag");
  const updateUser = useUpdateUser();

  const combinedErrors = {
    ...(updateUser.error || {}),
    ...(authError ? { old_password: authError } : {}),
  };

  return (
    <>
      {user.isPending && <Spinner text="Loading..." />}
      {user.isError && (
        <NotificationBanner severity="negative">
          {user.error.message}
        </NotificationBanner>
      )}
      {user.isSuccess && user.data && (
        <FormikForm<
          UserUpdateRequest & {
            passwordConfirm: UserUpdateRequest["password"];
            oldPassword: UserUpdateRequest["password"];
          },
          UpdateUserError
        >
          aria-label={isSelfEditing ? "Edit your profile" : "Edit user"}
          errors={
            Object.keys(combinedErrors).length > 0 ? combinedErrors : null
          }
          initialValues={{
            username: user.data.username,
            password: "",
            passwordConfirm: "",
            oldPassword: "",
            is_superuser: user.data.is_superuser,
            first_name: user.data.first_name,
            last_name: user.data.last_name || "",
            email: user.data.email,
          }}
          onCancel={closeSidePanel}
          onSubmit={async (values) => {
            setAuthError(null);

            if (isSelfEditing && values.password && values.oldPassword) {
              try {
                await authenticate.mutateAsync({
                  body: {
                    username: values.username,
                    password: values.oldPassword,
                  },
                });
              } catch (error) {
                setAuthError(`Current password is incorrect: ${error}`);
                return;
              }
            }

            const updateData: UserUpdateRequest = {
              username: values.username,
              is_superuser: values.is_superuser,
              first_name: values.first_name,
              last_name: values.last_name,
              email: values.email,
            };

            // Only include password if it's being changed
            if (values.password && values.passwordConfirm) {
              updateData.password = values.password;
            }

            updateUser.mutate({
              headers: { ETag: eTag },
              path: { user_id: id },
              body: updateData,
            });
          }}
          onSuccess={() => {
            return queryClient
              .invalidateQueries({
                queryKey: getUserQueryKey({
                  path: { user_id: id },
                }),
              })
              .then(closeSidePanel);
          }}
          resetOnSave={true}
          saved={updateUser.isSuccess}
          saving={updateUser.isPending || authenticate.isPending}
          submitLabel={isSelfEditing ? "Save profile" : "Save user"}
          validationSchema={
            isSelfEditing && passwordVisible ? SelfEditUserSchema : UserSchema
          }
        >
          <FormikField
            autoComplete="username"
            help="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
            label={Labels.Username}
            name="username"
            required={true}
            type="text"
          />
          <FormikField label={Labels.FullName} name="last_name" type="text" />
          <FormikField
            label={Labels.Email}
            name="email"
            required={true}
            type="email"
          />
          {!isSelfEditing && (
            <FormikField
              label={Labels.MaasAdmin}
              name="is_superuser"
              type="checkbox"
            />
          )}
          {!passwordVisible && (
            <div className="u-sv2">
              <Button
                appearance="link"
                className="u-no-margin--bottom"
                data-testid="toggle-passwords"
                onClick={() => {
                  setPasswordVisible(!passwordVisible);
                }}
                type="button"
              >
                {Labels.ChangePassword}
              </Button>
            </div>
          )}
          {passwordVisible && (
            <>
              {isSelfEditing && (
                <FormikField
                  autoComplete="current-password"
                  label={Labels.CurrentPassword}
                  name="oldPassword"
                  required={true}
                  type="password"
                />
              )}
              <FormikField
                autoComplete="new-password"
                label={isSelfEditing ? Labels.NewPassword : Labels.Password}
                name="password"
                required={true}
                type="password"
              />
              <FormikField
                autoComplete="new-password"
                help="Enter the same password as before, for verification"
                label={
                  isSelfEditing ? Labels.NewPasswordAgain : Labels.PasswordAgain
                }
                name="passwordConfirm"
                required={true}
                type="password"
              />
            </>
          )}
        </FormikForm>
      )}
    </>
  ) as React.ReactElement;
};

export default EditUser;

import { useMemo } from "react";

import { useSelector } from "react-redux";

import { powerTypes as powerTypesSelectors } from "@/app/store/general/selectors";
import type { PowerParameters } from "@/app/store/types/node";

/**
 * Returns a memoized object of the initial power parameters from given power
 * types. Used to initialise Formik forms so React doesn't complain about
 * unexpected values. Parameters should be trimmed to only relevant parameters
 * on form submit.
 * @param initialParameters - The power parameters to initialize. Will override api defaults.
 * @param forChassis - Whether the power parameters should only be relevant for chassis.
 * @returns Power parameters to initialise form with.
 */
export const useInitialPowerParameters = (
  initialParameters: PowerParameters = {},
  forChassis = false
): PowerParameters => {
  const allPowerTypes = useSelector(powerTypesSelectors.get);
  const chassisPowerTypes = useSelector(powerTypesSelectors.canProbe);
  const powerTypes = forChassis ? chassisPowerTypes : allPowerTypes;

  return useMemo(
    () =>
      powerTypes.reduce<PowerParameters>((parameters, powerType) => {
        powerType.fields.forEach((field) => {
          // Some fields are shared across different power types. Only set the
          // initial value once.
          if (!(field.name in parameters)) {
            const initialValue =
              field.name in initialParameters
                ? initialParameters[field.name]
                : field.default;
            parameters[field.name] = initialValue;
          }
        });
        return parameters;
      }, {}),
    [initialParameters, powerTypes]
  );
};

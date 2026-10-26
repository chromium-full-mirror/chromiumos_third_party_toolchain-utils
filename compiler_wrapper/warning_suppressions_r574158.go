// Copyright 2025 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

func warningSuppressionsForLLVM_r574158(packageNameAndCategory string) []string {
	switch packageNameAndCategory {
	// Observed and suppressed on 8 builders during testing.
	// e.g., brask-cq: https://ci.chromium.org/b/8698633382201754641.
	case "chromeos-base/cdm-oemcrypto":
		return []string{"-Wno-deprecated-declarations"}
	// Observed and suppressed on 8 builders during testing.
	// e.g., brask-cq: https://ci.chromium.org/b/8698633382201754641.
	case "chromeos-base/cdm-oemcrypto-hw-test":
		return []string{"-Wno-deprecated-declarations"}
	// Observed and suppressed on 5 builders during testing.
	// e.g., brask-cq: https://ci.chromium.org/b/8698633382201754641.
	case "chromeos-base/cdm-oemcrypto-hw-test-wv14":
		return []string{"-Wno-deprecated-declarations"}
	// Observed and suppressed on 5 builders during testing.
	// e.g., brask-cq: https://ci.chromium.org/b/8698633382201754641.
	case "chromeos-base/cdm-oemcrypto-wv14":
		return []string{"-Wno-deprecated-declarations"}
	// Observed and suppressed on 3 builders during testing.
	// e.g., arm-generic-cq: https://ci.chromium.org/b/8698633379302681905.
	case "chromeos-base/chromeos-init":
		return []string{"-Wno-deprecated-declarations"}
	// Observed and suppressed on 61 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8698633388008551569.
	case "chromeos-base/vboot_reference":
		return []string{"-Wno-default-const-init-field-unsafe"}
	// Observed and suppressed on 63 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8698633388008551569.
	case "chromeos-base/vboot_reference-tests":
		return []string{"-Wno-default-const-init-field-unsafe"}
	// Observed and suppressed on 6 builders during testing.
	// e.g., amd64-generic-kernel-v6_1-cq: https://ci.chromium.org/b/8698633378551660225.
	case "sys-kernel/chromeos-kernel-6_1":
		return []string{"-Wno-attribute-warning"}
	// Observed and suppressed on 4 builders during testing.
	// e.g., amd64-generic-kernel-v6_12-cq: https://ci.chromium.org/b/8698633378753205569.
	case "sys-kernel/chromeos-kernel-6_12":
		return []string{"-Wno-attribute-warning", "-Wno-unterminated-string-initialization"}
	// Observed and suppressed on 18 builders during testing.
	// e.g., amd64-generic-kernel-v6_6-cq: https://ci.chromium.org/b/8698633378953080785.
	case "sys-kernel/chromeos-kernel-6_6":
		return []string{"-Wno-attribute-warning"}
	// Observed and suppressed on 1 builder during testing.
	// e.g., endeavour-cq: https://ci.chromium.org/b/8698633383063159121.
	case "sys-kernel/gasket":
		return []string{"-Wno-default-const-init-field-unsafe"}
	default:
		return nil
	}
}

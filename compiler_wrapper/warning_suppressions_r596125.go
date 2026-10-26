// Copyright 2026 The ChromiumOS Authors
// Use of this source code is governed by a BSD-style license that can be
// found in the LICENSE file.

package main

func warningSuppressionsForLLVM_r596125(packageNameAndCategory string) []string {
	switch packageNameAndCategory {
	// Observed and suppressed on 67 builders during testing.
	// e.g., amd64-generic-cq: https://ci.chromium.org/b/8672511972670170385.
	// Permanent suppression: BlueZ is deprecated and OWNERS requested no
	// further warning cleanup patches (b/567060657, crrev.com/c/8480331).
	case "net-wireless/bluez":
		return []string{"-Wno-incompatible-pointer-types"}
	// Observed and suppressed on 5 builders during testing.
	// e.g., arm-generic-cq: https://ci.chromium.org/b/8672511961157057569.
	case "sys-fs/ecryptfs-utils":
		return []string{"-Wno-incompatible-pointer-types"}
	default:
		return nil
	}
}

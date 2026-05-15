$(function () {
    function RosetteGeneratorViewModel(parameters) {
        var self = this;

        self.settingsViewModel = parameters[0];
        self.isInitializing = true;

        self.style = ko.observable("Bump");
        self.radius = ko.observable(50.0);
        self.height = ko.observable(5.0);
        self.count = ko.observable(12);
        self.phase = ko.observable(0.0);
        self.splitPercent = ko.observable(50.0);
        self.xCount = ko.observable(3);
        self.flatLength = ko.observable(8.0);
        self.autoPreview = ko.observable(true);
        self.exportDir = ko.observable("");
        self.fileNameInput = ko.observable("");

        self.status = ko.observable("Ready");
        self.svgMarkup = ko.observable("");
        self.heldPayload = ko.observable(null);
        self.mergeAvailable = ko.observable(false);
        self.mergedPayload = ko.observable(null);

        self.showSplit = ko.pureComputed(function () {
            return self.style() === "Concave+Convex";
        });

        self.showX = ko.pureComputed(function () {
            return self.style() === "X + 1";
        });

        self.showFlatLength = ko.pureComputed(function () {
            return self.style() === "Bead";
        });

        self.hasHeld = ko.pureComputed(function () {
            return !!self.heldPayload();
        });

        self.heldSummary = ko.pureComputed(function () {
            var held = self.heldPayload();
            if (!held) {
                return "";
            }
            return held.kind + " / Segments " + held.count + " / Radius " + held.radius;
        });

        self.canMerge = ko.pureComputed(function () {
            return self.hasHeld() && self.mergeAvailable();
        });

        self.defaultFileName = ko.pureComputed(function () {
            var style = (self.style() || "Rosette").toString().trim();
            if (!style) {
                style = "Rosette";
            }

            var count = parseInt(self.count(), 10);
            if (isNaN(count) || count < 1) {
                count = 1;
            }

            var radius = parseFloat(self.radius());
            var radiusToken;
            if (isNaN(radius)) {
                radiusToken = "0";
            } else if (Math.abs(radius - Math.round(radius)) < 1e-9) {
                radiusToken = String(Math.round(radius));
            } else {
                radiusToken = String(radius).replace(".", "p");
            }

            return style + "-" + count + "-R" + radiusToken;
        });

        self.fileName = ko.pureComputed({
            read: function () {
                var customName = (self.fileNameInput() || "").trim();
                if (customName) {
                    return customName;
                }
                return self.defaultFileName();
            },
            write: function (value) {
                self.fileNameInput(value || "");
            }
        });

        self.buildPayload = function () {
            return {
                kind: self.style(),
                radius: parseFloat(self.radius()),
                height: parseFloat(self.height()),
                count: parseInt(self.count(), 10),
                phase: parseFloat(self.phase()),
                split_percent: parseFloat(self.splitPercent()),
                x_count: parseInt(self.xCount(), 10),
                flat_length: parseFloat(self.flatLength())
            };
        };

        self.scheduleAutoPreview = function () {
            if (self.isInitializing || !self.autoPreview()) {
                return;
            }
            self.preview();
        };

        self.preview = function () {
            self.status("Generating preview...");
            self.mergedPayload(null);
            var payload = self.buildPayload();
            if (self.heldPayload()) {
                payload.held = self.heldPayload();
            }
            $.ajax({
                url: OctoPrint.getBlueprintUrl("rosettegenerator") + "preview",
                method: "POST",
                contentType: "application/json",
                data: JSON.stringify(payload)
            })
                .done(function (response) {
                    if (!response || !response.ok) {
                        self.status((response && response.error) || "Preview failed");
                        return;
                    }
                    self.svgMarkup(response.svg || "");
                    self.status("Preview updated");
                })
                .fail(function (xhr) {
                    var msg = "Preview failed";
                    if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
                        msg = xhr.responseJSON.error;
                    }
                    self.status(msg);
                });
        };

        self.holdCurrent = function () {
            self.heldPayload(self.buildPayload());
            self.mergedPayload(null);
            self.status("Current rosette held for merge");
        };

        self.resetHold = function () {
            self.heldPayload(null);
            self.mergedPayload(null);
            self.svgMarkup("");
            self.status("Hold cleared and plot reset");
        };

        self.mergeHeld = function () {
            if (!self.mergeAvailable()) {
                self.status("Merge unavailable: shapely is not installed");
                return;
            }
            if (!self.heldPayload()) {
                self.status("Hold a rosette first");
                return;
            }

            self.status("Merging held and current rosettes...");
            $.ajax({
                url: OctoPrint.getBlueprintUrl("rosettegenerator") + "merge",
                method: "POST",
                contentType: "application/json",
                data: JSON.stringify({
                    held: self.heldPayload(),
                    current: self.buildPayload()
                })
            })
                .done(function (response) {
                    if (!response || !response.ok || !response.svg) {
                        self.status((response && response.error) || "Merge failed");
                        return;
                    }
                    self.mergedPayload({
                        held: self.heldPayload(),
                        current: self.buildPayload()
                    });
                    self.svgMarkup(response.svg);
                    self.status("Merge complete");
                })
                .fail(function (xhr) {
                    var msg = "Merge failed";
                    if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
                        msg = xhr.responseJSON.error;
                    }
                    self.status(msg);
                });
        };

        self.saveDefaults = function () {
            self.status("Saving defaults...");
            $.ajax({
                url: OctoPrint.getBlueprintUrl("rosettegenerator") + "settings",
                method: "POST",
                contentType: "application/json",
                data: JSON.stringify({
                    settings: {
                        default_style: self.style(),
                        outer_radius: parseFloat(self.radius()),
                        amplitude: parseFloat(self.height()),
                        num_segments: parseInt(self.count(), 10),
                        phase: parseFloat(self.phase()),
                        split_percent: parseFloat(self.splitPercent()),
                        x_count: parseInt(self.xCount(), 10),
                        flat_length: parseFloat(self.flatLength()),
                        auto_preview: !!self.autoPreview(),
                        export_dir: self.exportDir()
                    }
                })
            })
                .done(function (response) {
                    if (!response || !response.ok) {
                        self.status((response && response.error) || "Save defaults failed");
                        return;
                    }
                    self.status("Defaults saved");
                })
                .fail(function (xhr) {
                    var msg = "Save defaults failed";
                    if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
                        msg = xhr.responseJSON.error;
                    }
                    self.status(msg);
                });
        };

        self.loadSettings = function () {
            self.status("Loading defaults...");
            $.ajax({
                url: OctoPrint.getBlueprintUrl("rosettegenerator") + "settings",
                method: "GET"
            })
                .done(function (response) {
                    if (!response || !response.ok || !response.settings) {
                        self.status((response && response.error) || "Failed to load defaults");
                        self.isInitializing = false;
                        return;
                    }

                    var settings = response.settings;
                    self.style(settings.default_style || "Bump");
                    self.radius(settings.outer_radius);
                    self.height(settings.amplitude);
                    self.count(settings.num_segments);
                    self.phase(settings.phase);
                    self.splitPercent(settings.split_percent);
                    self.xCount(settings.x_count);
                    self.flatLength(settings.flat_length);
                    self.autoPreview(!!settings.auto_preview);
                    self.exportDir(settings.export_dir || "");
                    self.mergeAvailable(!!response.merge_available);

                    self.isInitializing = false;

                    if (self.autoPreview()) {
                        self.preview();
                    } else {
                        self.status("Ready");
                    }
                })
                .fail(function (xhr) {
                    self.isInitializing = false;
                    var msg = "Failed to load defaults";
                    if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
                        msg = xhr.responseJSON.error;
                    }
                    self.status(msg);
                });
        };

        self.exportSvg = function () {
            self.status("Saving SVG...");
            var payload;

            if (self.mergedPayload()) {
                payload = {
                    held: self.mergedPayload().held,
                    current: self.mergedPayload().current,
                    export_merged: true,
                    export_dir: self.exportDir(),
                    filename: self.fileName()
                };
            } else {
                payload = {
                    kind: self.style(),
                    radius: parseFloat(self.radius()),
                    height: parseFloat(self.height()),
                    count: parseInt(self.count(), 10),
                    phase: parseFloat(self.phase()),
                    split_percent: parseFloat(self.splitPercent()),
                    x_count: parseInt(self.xCount(), 10),
                    flat_length: parseFloat(self.flatLength()),
                    export_dir: self.exportDir(),
                    filename: self.fileName()
                };
            }

            $.ajax({
                url: OctoPrint.getBlueprintUrl("rosettegenerator") + "export",
                method: "POST",
                contentType: "application/json",
                data: JSON.stringify(payload)
            })
                .done(function (response) {
                    if (!response || !response.ok) {
                        self.status((response && response.error) || "Export failed");
                        return;
                    }
                    self.status("SVG saved to " + (response.path || self.exportDir()));
                })
                .fail(function (xhr) {
                    var msg = "Export failed";
                    if (xhr && xhr.responseJSON && xhr.responseJSON.error) {
                        msg = xhr.responseJSON.error;
                    } else if (xhr && xhr.responseText) {
                        try {
                            var parsed = JSON.parse(xhr.responseText);
                            if (parsed && parsed.error) {
                                msg = parsed.error;
                            }
                        } catch (_ignored) {
                            // Keep default message when responseText is not JSON.
                        }
                    }
                    self.status(msg);
                });
        };

        self.browseExportDir = function () {
            var currentValue = self.exportDir() || "";
            var chosenValue = window.prompt("Enter the folder path where SVG files should be saved", currentValue);
            if (chosenValue !== null) {
                self.exportDir(chosenValue.trim());
            }
        };

        self.style.subscribe(self.scheduleAutoPreview);
        self.radius.subscribe(self.scheduleAutoPreview);
        self.height.subscribe(self.scheduleAutoPreview);
        self.count.subscribe(self.scheduleAutoPreview);
        self.phase.subscribe(self.scheduleAutoPreview);
        self.splitPercent.subscribe(self.scheduleAutoPreview);
        self.xCount.subscribe(self.scheduleAutoPreview);
        self.flatLength.subscribe(self.scheduleAutoPreview);
        self.autoPreview.subscribe(self.scheduleAutoPreview);

        self.onStartupComplete = function () {
            self.loadSettings();
        };
    }

    OCTOPRINT_VIEWMODELS.push({
        construct: RosetteGeneratorViewModel,
        dependencies: ["settingsViewModel"],
        elements: ["#tab_plugin_rosettegenerator"]
    });
});

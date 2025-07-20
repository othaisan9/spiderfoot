    tabs = [ "use", "type", "module" ];
    activeTab = "use";

    function submitForm() {
        // Use case tab uses radio buttons - they submit automatically
        if (activeTab == "use") {
            // Clear other lists when using use case
            $("#modulelist").val("");
            $("#typelist").val("");
        } else {
            // Handle module and type tabs - they use checkboxes
            list = "";
            $("[id^="+activeTab+"_]").each(function() {
                if ($(this).is(":checked")) {
                    list += $(this).attr('id') + ",";
                }
            });

            $("#"+activeTab+"list").val(list);
            // Clear the other list
            for (i = 0; i < tabs.length; i++) {
                if (tabs[i] != activeTab && tabs[i] != "use") {
                    $("#"+tabs[i]+"list").val("");
                }
            }
        }
    }

    function switchTab(tabname) {
        $("#"+activeTab+"table").hide();
        $("#"+activeTab+"tab").removeClass("active");
        $("#"+tabname+"table").show();
        $("#"+tabname+"tab").addClass("active");
        activeTab = tabname;
        if (activeTab == "use") {
            $("#selectors").hide();
        } else {
            $("#selectors").show();
        }
    }

    function selectAll() {
        $("[id^="+activeTab+"_]").prop("checked", true);
    }

    function deselectAll() {
        $("[id^="+activeTab+"_]").prop("checked", false);
    }

$(document).ready(function() {
    $("#usetab").click(function() { switchTab("use"); });
    $("#typetab").click(function() { switchTab("type"); });
    $("#moduletab").click(function() { switchTab("module"); });
    $("#btn-select-all").click(function() { selectAll(); });
    $("#btn-deselect-all").click(function() { deselectAll(); });
    $("#btn-run-scan").click(function() { submitForm(); });

    $('#scantarget').popover({ 'html': true, 'animation': true, 'trigger': 'focus'});
});

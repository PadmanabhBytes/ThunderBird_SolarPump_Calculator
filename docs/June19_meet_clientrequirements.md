Solar Calculator Requests/Comments
1. Location/System Operating Window – Can we please shift the location/system
operating window input data to the top of the calculator so it is the first user input and
can be used to develop the GPD calculation in subsequent Production & TDH
a. Operating window data
i. Year Round: Take annual average data
ii. Summer Use Only: April-September average
iii. Winter Use Only: October-March average
2. Production Calculation – We would like the calculator to follow the following logic for
production inputs from the customer
Step 1 – Calculate Proposed Gallons Per Day
The calculator shall use the customer-entered GPM and apply the predefined Thunderbird Solar
production formula to generate a proposed Gallons Per Day (GPD) value. This value will be
based on the location data and follow the below formula:
GPD = GPM INPUT x 6.5 x 60 x 1.1 x SOLAR ZONE COEFF
SOLAR ZONE COEFF TABLE – Solar zone calculated by location data provided in first input field
ZONE 5 = 1.08
ZONE 4 = 1
ZONE 3 = .92
ZONE 2 = .85
ZONE 1 = .78
The customer shall then be presented with:
"Based on your requested flow rate, the estimated daily water production is X GPD. Is this
acceptable?"
Options:
 Yes
 No
Step 2A – Customer Accepts Calculated GPD
If the customer selects Yes:
 The calculated GPD becomes the production target.
 The calculator proceeds to system sizing.
 A single results category is displayed.
 Results are prioritized according to the system prioritization logic defined later in this
document.
Step 2B – Customer Rejects Calculated GPD
If the customer selects No:
The customer is prompted to enter a desired GPD value.
The calculator shall then generate two independent result categories.
Category 1 – Closest to Requested GPM
Systems optimized to match the customer's originally requested flow rate.
Category 2 – Closest to Requested GPD
Systems optimized to match the customer-entered GPD target.
Each category shall independently apply all sizing, filtering, and prioritization logic described in
this document.
3. TDH Calculator
Offer the customer the ability to input the TDH themselves. If they do not know, they should
have a check box that says “Help Me Calculate” and that, when checked, will open up the
below fields for use. If the customer inputs the TDH field themselves than the calculator will
simply use that number instead of using the below inputs to calculate the number.
Please update the following fields to be required:
a. Static water level
b. Expected drawdown
c. Vertical Elevation (not currently required – they can input 0 if not needed)
d. System Pressure (not currently required – they can input 0 if not needed)
e. Friction Loss - Add a checkbox asking, “Is there a pipe run between the well head
and the destination?” If yes, produce the following required fields:
i. Pipe material
ii. Nominal pipe diameter (in)
iii. Pipe run length (horizontal/linear) (ft)
4. Recovery Rate
a. Recovery Rate – this field should be required unless they check a box next to the
field that is “Unknown”
b. If they check “Unknown” then the question, “Is there any concern of the well
running dry?” question populates.
i. If the customer answers No, the system sizing logic excludes the recovery
rate filters listed in the sizing logic section below
ii. If the customer answers YES, the recovery rate filter applies as does all
applicable warnings
5. Well Casing
a. 4” pumps – add warning to any quote where 4” inner diameter casing is selected
with ACDC 4” option
6. Generator/Grid Backup
a. Separate generator and grid backup in to alternative check boxes
i. If generator box is checked, add a pop up that says “AC/DC TBS Solar
Products require 1ph 230VAC power backup for optimal performance”
ii. If grid is selected, add pop up that says, “AC/DC TBS Solar Products
require 1ph 230VAC power backup for optimal performance” and “An AC
surge protector is required for grid use – this SKU will be added to your
final system selections.”
1. Add SKU 344-1001 – 300VAC AC Surge Protection Device to the
output of any system sized
7. Solar Racking/Solar Panel Data
a. Add a checkbox saying “If viable, would you like to use our racking kit design
around 2.5” schedule 40 pipe (used for both groundpost and crossbeam)?”
i. If yes, this will be used to qualify the racking matrix to use when sizing the
system
ii. If no, this will be used to qualify the racking matrix to use when sizing the
system
b. Solar Panel Dimensions
i. If the input width (or TBS panel default) exceeds 35” – this will be used in
racking matrix defined below
ii. If the input width < 35” – this will be used in racking matrix defined below
INSERT RACKING MATRICES
8. System controls: Add a links that show diagrams of each system option
a. Three main system diagrams
i. Electrical float
1. If selected, insert comment that states, all ACDC TBS products can
accept pump up or pump down 2 wire floats. DC ONLY TBS
products will include a 3w float switch as a part of the sales
package.
ii. Pressure system (irrigation/cabin/house)
1. If selected, please include existing dropdown for PSI input and
make it required.
2. If top end shut off psi Input field does not match the “System
Pressure Field” used on TDH inputs (ignore is TDH number is given
by the customer) flag the mismatch and create a warning that
states these fields must match
a. Ex. System pressure field = 40psi; pressure switch selection
= 30/50psi – the customer must update the system
pressure field to equal 50psi before proceeding
iii. Pressure switch + mechanical float
1. If the customer selects Pressure Switch + mechanical float – add
15PSI to the existing TDH calculation
a. Recommended pressure switch shutoff: Shutoff PSI must
exceed the PSI needed from switch to tank (assume switch
set at well head)
i. Shutoff PSI recommendation = If user inputs the
TDH field manually, simple include a message
stating, “Shutoff PSI must exceed the PSI required
to move water from the pressure switch location to
the tank. Please select a psi rating that meets this
requirement and include that rating below.
ii. If they input subfields of the TDH, please suggest
the shutoff psi rating as follows:
1. Shutoff PSI Rating =ROUNDUP(Elevation
gain + Friction Loss + 10PSI,-1)
2. PSI replaces downstream head: Deadhead
TDH includes PSI, subtract downstream
head from pressure switch
3. Use downstream head without pressure
switch cutoff to calc GPM and GPD for
system
9. Wire Sizing
Core Formulas
 Operating array voltage
Vmp_Array = Panel_Count_Series × Panel_Vmp × 0.95
The 0.95 is a derate factor.
 System power
System_Power = MIN(Panel_Count_Total × Panel_Watts, Pump_Max_Watts)
Pump full power caps used in the sheet:
3TBS-4H-AC = 900 W
6TBS-4H-AC = 1200 W
12TBS-4H-AC = 1400 W
7TBS-4C-AC = 1800 W
13TBS-4C-AC = 600 W
15TBS-4C-AC = 3000 W
25TBS-4C-AC = 1200 W
40TBS-4C-AC = 1800 W
 Amp draw
Amp_Draw = MIN((System_Power / Vmp_Array) × 1.05, 12)
The 1.05 is a safety factor, and 12A is the maximum current cap.
Wire Resistance Constants
#14 AWG = 0.002525 ohm/ft
#12 AWG = 0.001588 ohm/ft
#10 AWG = 0.000999 ohm/ft
#8 AWG = 0.0006282 ohm/ft
#6 AWG = 0.0003951 ohm/ft
Parallel panel connections
Total_Panel_Count = series_count × parallel_strings
Vmp_Array = series_count × Panel_Vmp × 0.95
System_Power = MIN(Total_Panel_Count × Panel_Watts, 3000)
Amp_Draw = MIN((System_Power / Vmp_Array) × 1.05, 12)
 Max wire length
Max_Length_ft = ROUNDDOWN((Allowed_Voltage_Drop × Vmp_Array) /(2 × Amp_Draw ×
Wire_Resistance_Ohm_Per_Ft),-1)
The 2 accounts for round-trip conductor distance.
The result is rounded down to the nearest 10 ft.
10. Pump System Sizing
Pump Product Categories
All qualifying systems shall be grouped into one of three product categories.
Category A
Stacked Impeller Pump + External Drive
Examples:
 TBS AC/DC Systems
 Variable Frequency Drive (VFD) Controlled Systems
Category B
Stacked Impeller Pump + Internal Motor Drive
Examples:
 Integrated Controller Motor Systems
Category C
Helical Rotor Pump
Examples:
 Helical Pump with External Drive
 Helical Pump with Internal Drive
For prioritization purposes, all helical designs are treated as a single category.
3. Candidate System Generation
The calculator shall first generate all systems capable of meeting:
 TDH requirement
 Production requirement (GPD)
 Applicable electrical requirements
Only after all viable systems are identified shall prioritization logic be applied.
4. Primary Prioritization Logic
The primary selection criteria shall be based on:
1. Pump Category
2. Solar Panel Count
The intent is to prefer certain product categories when the panel count penalty remains within
acceptable limits.
External Drive vs Helical Pump
The External Drive system shall be preferred when:
External Drive Panel Count ≤ Helical Panel Count + 2 Panels
Examples:
External Drive Helical Selected
8 Panels 7 Panels External
9 Panels 7 Panels External
10 Panels 7 Panels Helical
Maximum allowable panel penalty:
+2 Panels
External Drive vs Internal Drive Stacked Impeller
The External Drive system shall only be preferred when:
External Drive Panel Count = Internal Drive Panel Count
Examples:
External Drive Internal Drive Selected
8 Panels 8 Panels External
9 Panels 8 Panels Internal
8 Panels 7 Panels Internal
Any panel count advantage favors the lower-panel-count system.
Internal Drive Stacked Impeller vs Helical
The Internal Drive system shall be preferred when:
Internal Drive Panel Count ≤ Helical Panel Count + 1 Panel
Examples:
Internal Drive Helical Selected
8 Panels 8 Panels Internal
9 Panels 8 Panels Internal
10 Panels 8 Panels Helical
Maximum allowable panel penalty:
+1 Panel
5. Solar Racking Complexity Adjustment
Purpose
To account for installation complexity and material cost associated with additional ground-post
requirements.
The calculator shall utilize the separate racking algorithm that determines:
 Crossbeam length
 Number of ground posts required
Examples:
 Single Ground Post Rack
 Two Ground Post Rack
 Additional rack configurations as defined elsewhere
Helical Pump Preference Adjustment
If a Helical Pump solution requires fewer ground posts than either competing category:
 External Drive
 Internal Drive Stacked Impeller
Then the allowable panel-count advantage for those competing categories shall be reduced by
one panel.
Modified Comparison
External vs Helical
Normal Preference:
External ≤ Helical + 2 Panels
Adjusted Preference:
External ≤ Helical + 1 Panel
Internal vs Helical
Normal Preference:
Internal ≤ Helical + 1 Panel
Adjusted Preference:
Internal ≤ Helical + 0 Panels
(Equal panel count only)
Intent
The calculator shall give additional value to solutions that reduce:
 Ground posts
 Rack complexity
 Installation labor
 Material cost
6. Wire Gauge Feasibility Filter
Purpose
Prevent recommending systems that require unusually large conductors on short wire runs.
Filter Rule
Exclude any system that:
 Requires 8 AWG wire
 AND wire run distance is less than 300 feet
Formula:
IF
Required Wire Size = 8 AWG
AND
Wire Run < 300 ft
THEN
System = Excluded
Exception
8 AWG systems remain valid when:
Wire Run ≥ 300 ft
7. Recovery Rate Protection Filter
Purpose
Prevent recommendations that are likely to over-pump the well.
The calculator shall compare:
 Pump Operating GPM
 Well Recovery Rate (GPM)
Each product category shall utilize independent filtering thresholds.
Helical Pump Recovery Rule
Requirement:
Pump GPM ≤ Recovery Rate
Example:
Recovery = 5 GPM
Allowed:
 4 GPM
 5 GPM
Rejected:
 5.1 GPM
 6 GPM
Internal Drive Stacked Impeller Recovery Rule
Requirement:
Pump GPM ≤ Recovery Rate + 2.5 GPM
Example:
Recovery = 5 GPM
Allowed:
 5 GPM
 6 GPM
 7.5 GPM
Rejected:
 7.6 GPM+
External Drive Recovery Rule
Requirement:
Pump GPM ≤ Recovery Rate × 2.4
Example:
Recovery = 5 GPM
Allowed:
 Up to 12 GPM
Rejected:
 Greater than 12 GPM
8. Recovery Rate Warning Logic
Passing the recovery filter does not eliminate the need for a warning.
A warning shall be displayed whenever:
Pump GPM > Recovery Rate
Helical Warning
This condition should rarely occur due to filtering logic.
If implemented:
Warning: Pump output exceeds the reported well recovery rate. Continuous operation may
result in the well being pumped down.
Internal Drive Warning
Warning: Pump output exceeds the reported well recovery rate. This system may require
storage capacity, timer controls, or additional well recovery evaluation.
External Drive Warning
Warning: Pump output exceeds the reported well recovery rate. Variable speed operation may
allow successful operation, however storage capacity and well recovery characteristics should
be reviewed before installation.
9. Recommended Selection Process
The calculator should execute in the following order:
1. Receive customer inputs.
2. Calculate proposed GPD.
3. Determine single-output or dual-output workflow.
4. Generate all candidate systems meeting TDH and production requirements.
5. Apply wire gauge feasibility filter.
6. Apply recovery-rate filter.
7. Apply panel-count prioritization.
8. Apply racking-complexity adjustment.
9. Select highest-priority system(s).
10. Apply recovery-rate warnings where applicable.
11. Present final recommendation(s) to the customer.
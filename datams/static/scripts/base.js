function highlight_row () {
  let tid = String(this.parentElement.parentElement.parentElement.id);
  let table = tables.get(tid);
  if (typeof table.cell(this).index() !== 'undefined') {
    let rowIdx = table.cell(this).index().row;
    let cells = table.cells();
    for (let i = 0; i < cells[0].length; i++){
      if (cells[0][i].row == rowIdx){
         cells.nodes()[i].classList.add('highlight');
      }
    }
  }
}

function unhighlight_row () {
  let tid = String(this.parentElement.parentElement.parentElement.id);
  let table = tables.get(tid);
  table.cells().nodes().each((el) => el.classList.remove('highlight'));
}

function to_url () {
  let tid = String(this.parentElement.parentElement.parentElement.id);
  let table = tables.get(tid);
  
  let url = true;      // table.columns().names().includes('url');
  let unlink = false;  // table.columns().names().includes('unlink');
  
  
  let colIdx = table.cell(this).index().column;
  let rowIdx = table.cell(this).index().row;
  
  let data = table.row(rowIdx).data();
  let ncols = table.columns()[0].length;
  
  //console.log(url)
  //console.log(ncols)
  //console.log(colIdx)
  //console.log(unlink)
  
  if (url && unlink) {
    if (colIdx != (ncols - 3)) {
      window.location = data[ncols - 2];  // url
    } else {
      window.location = data[ncols - 1];  // unlink
    }
  }else if (url && !unlink) {
    window.location = data[ncols-1];  // url
  }else if (!url && unlink) {
    if (colIdx == (ncols - 2)) {
      window.location = data[ncols - 1];  // unlink
    }
  }
}

function px_to_val(px) {
  return parseInt(px.slice(0,-2));
}

function val_to_px(val) {
  return val.toString() + "px";
}

function available_height() {
  let height = window.innerHeight;
  let elements = ["navbar", "banner"];
  for (let i =0; i < elements.length; i++) {
    let element = document.getElementById(elements[i]);
    // style = window.getComputedStyle(element);
    // height -= (px_to_val(style.marginTop) + px_to_val(style.height) + px_to_val(style.marginBottom));
    height -= element.clientHeight;
  }
  console.log(height)
  return val_to_px(height);
}

function resize_contents() {
   var contents = document.getElementById("contents");
   console.log(available_height());
   contents.style.height = available_height();
   /* for (let child of e.children) {
    console.log(child.style);
    child.style.height = h;
  } */
}

function format_table(tid, dom, paging, pagelength, lengthmenu, header, highlight, selectable, serverside) {
  //For additional references see: https://datatables.net/examples/styling/bootstrap5.html
  
  // Check table header to see if the last column is 'url' if it is then we hide it set the onclick methods
  // console.log(document.getElementById(tid).children[0].children[0].children);
  let headers = document.getElementById(tid).children[0].children[0].children;
  let url = headers[headers.length -1].innerText == 'url';
  let columnDefs = [];
  if (url) {
    columnDefs.push({ target: -1, searchable: false, sortable: false, visible: false, searchable: false});
  }
  if (selectable) {
    var buttons = [
        {
            "text": 'Select All',
            "extend": 'selectAll',
            "selectorModifier": {
                "search": 'applied'
            }
        },
        {
            "text": 'Select Page',
            "extend": 'selectAll',
            "selectorModifier": function () {
                return {page: 'current'}
            }
        },
        'selectNone'
    ];
  } else {
    var buttons = [];
  }
  
  if (serverside == "") {
    // initialize table
    var table = new DataTable(
      '#' + tid, {
          "dom": dom,
          "paging": paging,
          "select": selectable,
          "lengthMenu": lengthmenu,
          "pageLength": pagelength,
          "buttons": buttons,
          // "stateSave": true,  // turn this off when changing other options to make debugging easier
          "columnDefs": columnDefs,
      }
    );
  } else {
    var table = new DataTable(
      '#' + tid, {
          "serverSide": true,
          "ajax": serverside,
          "dom": dom,
          "paging": paging,
          "select": selectable,
          "lengthMenu": lengthmenu,
          "pageLength": pagelength,
          "buttons": buttons,
          // "stateSave": true,  // turn this off when changing other options to make debugging easier
          "columnDefs": columnDefs,
      }
    );
  }

  
  // add the table to our map
  tables.set(tid, table);

  // set the click action to navigate to url if the url column is at the end
  if (url) {
    table.on('click', 'tbody td', to_url);
  }
  
  // hide the header row if chosen
  if (!header) {
    document.getElementById(tid).children[0].style.display = "none";
  }

  // highlight row and make cursor pointer when hovered if chosen
  if (highlight && !selectable) {
    table.on('mouseenter', 'td', highlight_row);
    table.on('mouseleave', 'td', unhighlight_row);
  }
  
  if (selectable) {
    table.cells().nodes().each((el) => el.classList.add('selectable'));
  }
  
  document.getElementById(tid + '_loader').classList.add('d-none');
  document.getElementById(tid).classList.remove('d-none');
}

function formatMap(id, center, zoom, points) {
  let map = new google.maps.Map(
    document.getElementById(id),
    {
      zoom: zoom,
      center: center,
      mapTypeId: "roadmap",  // 'roadmap' | 'satellite' | 'hybrid' | 'terrain'
    }
  );
  // add the table to our map
  gmaps.set(id, map);
  
  let infowindows = [];
  let markers = [];
  for (let i = 0; i < points.length; i++) {
    infowindows[i] = new google.maps.InfoWindow({
        content: points[i].get("html"), 
        ariaLabel: points[i].get("hydrophones")
    });
    markers[i] = new google.maps.Marker({
      position: {lat: points[i].get("latitude"), lng: points[i].get("longitude")},
      map: map,
      title: points[i].get("hydrophones"),
      icon: {
        path: points[i].get("icon"),
        fillColor: points[i].get("color"),
        fillOpacity: 1,
        labelOrigin: new google.maps.Point(12, -12),
        strokeWeight: 1,
        strokeColor: "#000000",
        scale: 1,
      },
      label: points[i].get("hydrophones"),
    });
    markers[i].addListener("click", () => {
      infowindows[i].open({anchor: markers[i], map});
    });
  }  
}

function addOrganizationField() {
  let first_organization = document.getElementById('organization_id');
  let additional_organizations = document.getElementById('additionalOrganizations');
  let idx = additional_organizations.children.length + 1;
  let values = [first_organization.value];
  for (let i=0; i < additional_organizations.children.length; i++){
      values[i+1] = additional_organizations.children[i].value;
  }
  if (organization_options.length > idx) {  
    let select = document.createElement('select');
    select.id = "organization_id" + idx.toString();
    select.name = "organization_id" + idx.toString();
    select.classList.add("form-select");
    select.required = true;
    select.addEventListener('change', updateOrganizationOptions);
    additional_organizations.appendChild(select);
    
    let default_option = document.createElement('option');
    default_option.value = "";
    default_option.selected = true;
    default_option.disabled = true;
    default_option.hidden = true;
    default_option.textContent = "Choose...";
    select.appendChild(default_option);
    
    for (let i=0; i < organization_options.length; i++){
      if (!values.includes(organization_options[i].value)){
        select.appendChild(organization_options[i].cloneNode(true));
      }
    }
  }
}
function removeOrganizationField() {
  let ao = document.getElementById('additionalOrganizations');
  if (ao.children.length > 0){
    ao.children[ao.children.length-1].remove();
  }
}

function updateOrganizationOptions() {
  let selects = [];
  let values = [];
  selects[0] = document.getElementById('organization_id');
  values[0] = document.getElementById('organization_id').value;
  let additional_organizations = document.getElementById('additionalOrganizations');
  for (let i=0; i < additional_organizations.children.length; i++){
    selects[i+1] = additional_organizations.children[i];
    values[i+1] = additional_organizations.children[i].value;
  }
  for (let i=0; i < selects.length; i++){
    while(selects[i].children.length > 1){
      selects[i].removeChild(selects[i].lastChild);
    }
    for (let j=0; j < organization_options.length; j++){
      if (!values.includes(organization_options[j].value) || organization_options[j].value == values[i]){
        selects[i].appendChild(organization_options[j].cloneNode(true));
      }
      selects[i].value = values[i];
    }
  }
}

function levelChanged() {
  let e = document.getElementById('level');
  if(e.value == 'unowned') {
    document.getElementById('organization_id').parentElement.classList.add('d-none');
    document.getElementById('deployment_id').parentElement.classList.add('d-none');
    document.getElementById('mooring_id').parentElement.classList.add('d-none');
    document.getElementById('equipment_id').parentElement.classList.add('d-none');
    document.getElementById('organization_id').required = false;
    document.getElementById('deployment_id').required = false;
    document.getElementById('mooring_id').required = false;
    document.getElementById('equipment_id').required = false;
  }
  else if(e.value == 'organization') {
    document.getElementById('organization_id').parentElement.classList.remove('d-none');
    document.getElementById('deployment_id').parentElement.classList.add('d-none');
    document.getElementById('mooring_id').parentElement.classList.add('d-none');
    document.getElementById('equipment_id').parentElement.classList.add('d-none');
    document.getElementById('organization_id').required = true;
    document.getElementById('deployment_id').required = false;
    document.getElementById('mooring_id').required = false;
    document.getElementById('equipment_id').required = false;
  }else if (e.value == 'deployment'){
    document.getElementById('organization_id').parentElement.classList.remove('d-none');
    document.getElementById('deployment_id').parentElement.classList.remove('d-none');
    document.getElementById('mooring_id').parentElement.classList.add('d-none');
    document.getElementById('equipment_id').parentElement.classList.add('d-none');
    document.getElementById('organization_id').required = true;
    document.getElementById('deployment_id').required = true;
    document.getElementById('mooring_id').required = false;
    document.getElementById('equipment_id').required = false;
  }else if (e.value == 'mooring_equipment'){
    document.getElementById('organization_id').parentElement.classList.remove('d-none');
    document.getElementById('deployment_id').parentElement.classList.remove('d-none');
    document.getElementById('mooring_id').parentElement.classList.remove('d-none');
    document.getElementById('equipment_id').parentElement.classList.remove('d-none');
    document.getElementById('organization_id').required = true;
    document.getElementById('deployment_id').required = true;
    document.getElementById('mooring_id').required = true;
    document.getElementById('equipment_id').required = true;
  }
  let event = new Event('change');
  let organization = document.getElementById('organization_id');
  organization.dispatchEvent(event);
}

function organizationChanged(){
  let oid = document.getElementById('organization_id').value;
  let deployment = document.getElementById('deployment_id');
  while(deployment.children.length > 1){
    deployment.removeChild(deployment.lastChild);
  }
  if (oid != ''){
    for (let i=0; i < deployment_map.get(oid).length; i++){
      deployment.append(deployment_options[deployment_map.get(oid)[i]].cloneNode(true));
    }
  }
  if (deployment.children.length > 1){
    deployment.children[1].selected = true;
  } else {
    deployment.children[0].selected = true;
  }
  let event = new Event('change');
  deployment.dispatchEvent(event);
}

function deploymentChanged(){
  did = document.getElementById('deployment_id').value;
  let mooring = document.getElementById('mooring_id');
  while(mooring.children.length > 1){
    mooring.removeChild(mooring.lastChild);
  }
  if (did != ''){
    for (let i=0; i < mooring_map.get(did).length; i++){
      mooring.append(mooring_options[mooring_map.get(did)[i]].cloneNode(true));
    }
  }
  if (mooring.children.length > 1){
    mooring.children[1].selected = true;
  } else {
    mooring.children[0].selected = true;
  }
  let event = new Event('change');
  mooring.dispatchEvent(event);
}

function mooringChanged(){
  mid = document.getElementById('mooring_id').value;
  let equipment = document.getElementById('equipment_id');
  while(equipment.children.length > 1){
    equipment.removeChild(equipment.lastChild);
  }
  if (mid != ''){
    for (let i=0; i < equipment_map.get(mid).length; i++){
      equipment.append(equipment_options[equipment_map.get(mid)[i]].cloneNode(true));
    }
  }
  if (equipment.children.length > 1){
    equipment.children[1].selected = true;
  } else {
    equipment.children[0].selected = true;
  }
  let event = new Event('change');
  equipment.dispatchEvent(event);
}

function arrayToTable(tableData) {
    var table = $('<table></table>');
    table.id = "csvTable";
    $(tableData).each(function (i, rowData) {
        if (i == 0){
          var row = $('<th></th>');
        } else {
          var row = $('<tr></tr>');
        }
        $(rowData).each(function (j, cellData) {
            row.append($('<td>'+cellData+'</td>'));
        });
        table.append(row);
    });
    return table;
}

const organization_options = [];
const deployment_options = [];
const mooring_options = [];
const equipment_options = [];

const deployment_map = new Map();
const mooring_map = new Map();
const equipment_map = new Map();

const tables = new Map();
const gmaps = new Map();

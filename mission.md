## Summary
This app is a way to visualize structural calculations, and how they map onto structural elements. We want to be able to take beams / columns / connections / screws for connections, every thing that can be sized in a strucuture, and create a clear link between the visualization and calculations. It's assumed that the calcualtions are human readable, in pdf form.

It's assumed that unless state otherwise, pdfs are either one to one with calculations, or in one large pdf. We may have multiple versions of each pdf.

To produce the element graph we need BIM rich input - currently we use IFC imports with a converter that produces the graph. It's assumed that there be a IFC input (user uploads IFC), but we could have many different types of parses. We then want to take that IFC input and and produce our element graph. This element graph can be mapped onto the calculation graph.

There are two graphs, the structural calculation graph, and the structural element graph. We want to be able to map the two graphs of eachother.

The goal of the structural calcualtion graph will be to easily view the claculations and types of calculations (beams/columns/connections) that are in the structures. 
Using the calculation graph, we wil be able to view the actual calculation source - the app data is linked to the pdf. There will be several different views for the element graphs which have not all been developed yet.

The goal of the structual element graph is to model connectivity of the structural elements in the. We have structural elements (our beams columns etc) and connections. We need a system that can link connectivty, so we can say beam A101 is connected to column C2012.


## UI
UI is very important. The outputs need to be of the highest quality and you should think a lot about how things look. Look at UI skills, and if you can't find any download them from the internet.

use react + typescript for the UI.


EVERYTHING AFTER THIS LINE IS A WORK IN PROGRESS, DO NOT INCLUDE IT.

## 
**views**
There is a 3D view of our model.
There are two main types of views for the graph:
- the calculation graph view
- the element graph view

## THe calculation graph view will 

## Structural Element graph
We need to create a topological map of beams


Both views will show elements in a graph like form.

Interactions we want:
- We want to see the whole building in 3D. We should be able to click an element and see the pdf calcualtion information of that element.
- When we click on elements within the graph, we should be able to 
